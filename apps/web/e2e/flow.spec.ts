import { expect, test, type Browser, type Page } from "@playwright/test";
import { totp } from "./totp";

const ADMIN = { username: "e2e-admin", password: "e2e-admin-password-1" };
const NEWS =
  "The central bank announced on Monday that it will keep its benchmark interest rate unchanged " +
  "for a third consecutive meeting, citing slowing inflation and uncertainty in global energy markets.";

// 2FA secrets of accounts enrolled earlier in this run, so a user can sign in again in a later test.
const knownSecrets = new Map<string, string>();

async function signIn(page: Page, username: string, password: string, secret?: string) {
  secret ??= knownSecrets.get(username);
  await page.goto("/login");
  await page.getByLabel("نام کاربری").fill(username);
  await page.getByLabel("گذرواژه").fill(password);
  await page.getByRole("button", { name: "ادامه" }).click();
  if (!secret) {
    // First login: 2FA enrolment is forced; read the manual key shown next to the QR code.
    secret = (await page.locator("code").innerText()).trim();
    knownSecrets.set(username, secret);
  }
  await page.getByLabel("کد ۶‌رقمی برنامه احراز هویت").fill(totp(secret));
  await page.getByRole("button", { name: /فعال‌سازی و ورود|^ورود$/ }).click();
  await expect(page.getByRole("heading", { name: "رصد", level: 2 })).toBeVisible();
  return secret;
}

async function userPage(browser: Browser, username: string, password: string) {
  const ctx = await browser.newContext({
    baseURL: test.info().project.use.baseURL,
    locale: "fa-IR",
  });
  const page = await ctx.newPage();
  await signIn(page, username, PASSWORD);
  return page;
}

const PASSWORD = "e2e-user-password-1";

// The admin enrols 2FA once; every later test only needs the accounts created here.
test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({
    baseURL: test.info().project.use.baseURL,
    locale: "fa-IR",
  });
  const page = await ctx.newPage();
  await signIn(page, ADMIN.username, ADMIN.password);
  for (const [username, role] of [
    ["e2e-lead", "content_lead"],
    ["e2e-editor", "diplomatic_editor"],
    ["e2e-operator", "ai_operator"],
    ["e2e-analyst", "trend_analyst"],
    ["e2e-boss", "president_office"],
    ["e2e-strategist", "narrative_strategist"],
  ]) {
    const r = await page.request.post("/api/admin/users", {
      headers: { "x-ncr": "1" },
      data: { username, display_name: username, password: PASSWORD, role },
    });
    expect(r.status()).toBe(201);
  }
  await ctx.close();
});

test("signal → draft → approval → published", async ({ browser }) => {
  // --- content lead: paste news → analysed signal within 30 s ---
  const lead = await userPage(browser, "e2e-lead", PASSWORD);
  await lead.getByRole("textbox", { name: "متن خبر یا توییت" }).fill(NEWS);
  await lead.getByRole("button", { name: "افزودن و تحلیل" }).click();
  await expect(
    lead.getByRole("heading", { name: "بانک مرکزی نرخ بهره را ثابت نگه داشت" }),
  ).toBeVisible({
    timeout: 30_000,
  });
  await expect(lead.getByText("ریسک کم").first()).toBeVisible();

  // --- studio: three distinct angles, over-limit tweet flagged ---
  await lead.getByRole("button", { name: "تولید محتوا" }).click();
  await lead.getByRole("button", { name: "تولید سه پیشنهاد" }).click();
  const studio = lead.getByRole("region", { name: "استودیوی محتوا" });
  await expect(studio.getByRole("article")).toHaveCount(3);
  await expect(studio.getByText("ثبات و پیش‌بینی‌پذیری")).toBeVisible();
  await expect(studio.getByText("نگاه تمدنی")).toBeVisible();
  await expect(studio.getByText("بیش از حد مجاز")).toHaveCount(1);
  await expect(studio.locator("textarea[aria-invalid=true]")).toHaveCount(1);

  // --- the review runs by itself; the lead cannot approve her own draft ---
  const card = studio.getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" });
  const reviewPanel = card.getByRole("region", { name: "بررسی لحن" });
  await expect(reviewPanel.getByText("امتیاز ۸۸")).toBeVisible();
  await expect(reviewPanel.getByText("قلاب می‌تواند قوی‌تر باشد")).toBeVisible();
  await expect(card.getByText("در انتظار تأیید")).toBeVisible();
  await expect(card.getByRole("button", { name: "تأیید انتشار" })).toHaveCount(0);

  // --- the editor approves publication (low risk: no extra question) ---
  const editor = await userPage(browser, "e2e-editor", PASSWORD);
  const queue = editor.getByRole("region", { name: "صف انتشار" });
  const queued = queue.getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" });
  await queued.getByRole("button", { name: "تأیید انتشار" }).click();
  await expect(queued.getByRole("button", { name: "تأیید انتشار" })).toHaveCount(0);

  // --- lead records publication (after manual posting on X) ---
  lead.on("dialog", (d) => d.accept());
  await lead.reload();
  const leadQueue = lead.getByRole("region", { name: "صف انتشار" });
  await leadQueue
    .getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" })
    .getByRole("button", { name: "ثبت انتشار" })
    .click();
  await expect(
    leadQueue
      .getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" })
      .getByRole("button", { name: "ثبت انتشار" }),
  ).toHaveCount(0);
});

test("red lines: reviewers edit the list, other roles only read it", async ({ browser }) => {
  const editor = await userPage(browser, "e2e-editor", PASSWORD);
  await editor.getByRole("link", { name: "خطوط قرمز" }).click();
  await expect(editor.getByRole("heading", { name: "خطوط قرمز", level: 1 })).toBeVisible();
  await expect(editor.getByText("عملیات نظامی")).toBeVisible(); // starter list from the voice guide

  await editor.getByPlaceholder("موضوع یا عبارت").fill("تحریم‌های بانکی");
  await editor.getByRole("button", { name: "افزودن" }).click();
  const item = editor.getByRole("listitem").filter({ hasText: "تحریم‌های بانکی" });
  await expect(item).toBeVisible();
  await item.getByRole("button", { name: "غیرفعال" }).click();
  await expect(item.getByRole("button", { name: "فعال‌سازی" })).toBeVisible();

  const lead = await userPage(browser, "e2e-lead", PASSWORD);
  await lead.goto("/redlines");
  await expect(lead.getByText("تحریم‌های بانکی")).toBeVisible();
  await expect(lead.getByRole("button", { name: "افزودن" })).toHaveCount(0);
});

test("morning overview lists analysed signals and sends one to the studio", async ({ browser }) => {
  const strategist = await userPage(browser, "e2e-strategist", PASSWORD);
  await strategist
    .getByRole("textbox", { name: "متن خبر یا توییت" })
    .fill(
      "The central bank signalled a pause in rate decisions while regional exporters asked for clearer currency guidance this week.",
    );
  await strategist.getByRole("button", { name: "افزودن و تحلیل" }).click();

  const overview = strategist.getByRole("region", { name: /مرور هوشمند/ });
  const row = overview
    .getByRole("listitem")
    .filter({ hasText: "بانک مرکزی نرخ بهره را ثابت نگه داشت" });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row.getByText("ورود فعال")).toBeVisible();
  await row.getByRole("button", { name: "تولید محتوا" }).click();
  await expect(strategist.getByRole("button", { name: "تولید سه پیشنهاد" })).toBeVisible();
});

test("sources: analysts manage them, other roles only see health", async ({ browser }) => {
  const analyst = await userPage(browser, "e2e-analyst", PASSWORD);
  await analyst.getByRole("link", { name: "منابع" }).click();
  await expect(analyst.getByRole("heading", { name: "منابع رصد", level: 1 })).toBeVisible();
  const list = analyst.getByRole("list", { name: "منابع" });
  await expect(list.getByText("BBC World")).toBeVisible(); // starter list

  await analyst.getByPlaceholder("نام منبع").fill("منبع آزمایشی");
  await analyst
    .getByPlaceholder("https://example.com/rss.xml")
    .fill("https://example.com/feed.xml");
  await analyst.getByRole("button", { name: "افزودن منبع" }).click();
  const item = list.getByRole("listitem").filter({ hasText: "منبع آزمایشی" });
  await expect(item).toBeVisible();
  await item.getByRole("button", { name: "غیرفعال" }).click();
  await expect(item.getByRole("button", { name: "فعال‌سازی" })).toBeVisible();

  const lead = await userPage(browser, "e2e-lead", PASSWORD);
  await lead.goto("/sources");
  await expect(lead.getByText("منبع آزمایشی")).toBeVisible();
  await expect(lead.getByRole("button", { name: "افزودن منبع" })).toHaveCount(0);
});

test("reports: an analyst builds one and the team is notified", async ({ browser }) => {
  const analyst = await userPage(browser, "e2e-analyst", PASSWORD);
  await analyst.getByRole("link", { name: "گزارش‌ها" }).click();
  await analyst.getByRole("button", { name: /ساخت گزارش همین حالا/ }).click();
  await expect(analyst.getByRole("heading", { name: "گزارش دستی", level: 1 })).toBeVisible();
  await expect(
    analyst.getByRole("region", { name: "خلاصه" }).getByText("خلاصه آزمایشی"),
  ).toBeVisible();
  await expect(analyst.getByRole("region", { name: "مهم‌ترین‌ها" })).toBeVisible();

  const lead = await userPage(browser, "e2e-lead", PASSWORD);
  await lead.getByRole("button", { name: /اعلان‌ها/ }).click();
  await lead.getByRole("menuitem", { name: /گزارش هوش/ }).click();
  await expect(lead.getByRole("heading", { name: "گزارش دستی", level: 1 })).toBeVisible();
  await lead.goto("/");
  await lead.getByRole("button", { name: /اعلان‌ها/ }).click();
  await expect(lead.getByRole("menuitem", { name: /گزارش هوش/ })).toBeVisible();
  await expect(
    lead.getByRole("button", { name: "علامت‌گذاری همه به‌عنوان خوانده‌شده" }),
  ).toHaveCount(0); // all read
});

test("high-risk drafts are labelled, get their own tab and need an explicit yes", async ({
  browser,
}) => {
  const lead = await userPage(browser, "e2e-lead", PASSWORD);
  const studio = lead.getByRole("region", { name: "استودیوی محتوا" });
  await studio
    .getByPlaceholder("موضوع را بنویسید یا از ستون رصد یک سیگنال انتخاب کنید")
    .fill("وضعیت منطقه");
  await studio.getByRole("button", { name: "تولید سه پیشنهاد" }).click();
  await expect(studio.getByRole("article")).toHaveCount(3);

  // The editor touches a red-line topic: the review finds it and the risk goes up by itself.
  const text = studio.getByRole("article").first().locator("textarea");
  await text.fill("گزارش‌هایی درباره عملیات نظامی جدید در منطقه منتشر شده است.");
  await text.blur();
  const risky = studio.getByRole("article").filter({ hasText: "⚠ پرریسک" });
  await expect(risky).toHaveCount(1, { timeout: 30_000 });
  await expect(
    risky.getByRole("region", { name: "بررسی لحن" }).getByText("موضوع خط قرمز: عملیات نظامی"),
  ).toBeVisible();

  const pipeline = lead.getByRole("region", { name: "صف انتشار" });
  await pipeline.getByRole("tab", { name: /پرریسک/ }).click();
  await expect(pipeline.getByRole("article")).toHaveCount(1);
  await expect(pipeline.getByRole("tab", { name: /پرریسک/ })).toContainText("۱");

  // A normal approver cannot approve it; the President's Office must, and is asked to confirm.
  const editor = await userPage(browser, "e2e-editor", PASSWORD);
  await editor
    .getByRole("region", { name: "صف انتشار" })
    .getByRole("tab", { name: /پرریسک/ })
    .click();
  await expect(editor.getByText("تأیید پرریسک با نقش دارای دسترسی")).toBeVisible();

  const boss = await userPage(browser, "e2e-boss", PASSWORD);
  let asked = "";
  boss.on("dialog", (d) => {
    asked = d.message();
    d.accept();
  });
  const bossQueue = boss.getByRole("region", { name: "صف انتشار" });
  await bossQueue.getByRole("tab", { name: /پرریسک/ }).click();
  const item = bossQueue.getByRole("article").first();
  await item.getByRole("button", { name: "تأیید انتشار" }).click();
  await expect(item.getByRole("button", { name: "لغو تأیید" })).toBeVisible(); // now approved
  expect(asked).toContain("پرریسک");
});

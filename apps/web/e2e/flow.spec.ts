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

  // --- lead submits; cannot approve their own draft ---
  const card = studio.getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" });
  await card.getByRole("button", { name: "ارسال به بازبینی" }).click();
  await expect(card.getByText("در انتظار ویراستار دیپلماتیک")).toBeVisible();
  await expect(card.getByRole("button", { name: "تأیید" })).toHaveCount(0);

  // --- diplomatic editor approves ---
  const editor = await userPage(browser, "e2e-editor", PASSWORD);
  const queue = editor.getByRole("region", { name: "صف انتشار" });
  await queue
    .getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" })
    .getByRole("button", { name: "تأیید" })
    .click();
  await expect(
    queue
      .getByRole("article", { name: "ثبات و پیش‌بینی‌پذیری" })
      .getByRole("button", { name: "تأیید" }),
  ).toHaveCount(0);

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

test("knowledge base: upload, search, and sensitive documents fail closed", async ({ browser }) => {
  const op = await userPage(browser, "e2e-operator", PASSWORD);
  await op.getByRole("link", { name: "پایگاه دانش" }).click();
  await expect(op.getByRole("heading", { name: "پایگاه دانش", level: 1 })).toBeVisible();

  const upload = async (name: string, text: string, sensitivity: string) => {
    await op.locator('input[type="file"]').setInputFiles({
      name: `${name}.txt`,
      mimeType: "text/plain",
      buffer: Buffer.from(text),
    });
    await op.getByLabel("طبقه حساسیت").first().selectOption(sensitivity);
    await op.getByRole("button", { name: "بارگذاری سند" }).click();
  };

  await upload("identity", "تمدن ایرانی بر گفت‌وگو و حافظه مشترک بنا شده است.", "normal");
  const docs = op.getByRole("list", { name: "اسناد" });
  await expect(docs.getByText("آماده")).toBeVisible({ timeout: 20_000 });

  await op
    .getByRole("searchbox", { name: "جست‌وجو" })
    .or(op.getByLabel("جست‌وجو"))
    .fill("حافظه مشترک");
  await op.getByRole("button", { name: "جست‌وجو" }).click();
  await expect(
    op.getByRole("region", { name: "نتایج جست‌وجو" }).getByText("identity.txt"),
  ).toBeVisible();

  // This stack has no local model, so a sensitive document must fail instead of going to the cloud.
  await upload("secret", "پروتکل داخلی بحران: تماس با دفتر رئیس.", "sensitive");
  await expect(docs.getByText("ناموفق")).toBeVisible({ timeout: 20_000 });
  await expect(docs.getByText("آماده")).toHaveCount(1);
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

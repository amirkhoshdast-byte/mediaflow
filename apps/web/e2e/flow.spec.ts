import { expect, test, type Browser, type Page } from "@playwright/test";
import { totp } from "./totp";

const ADMIN = { username: "e2e-admin", password: "e2e-admin-password-1" };
const NEWS =
  "The central bank announced on Monday that it will keep its benchmark interest rate unchanged " +
  "for a third consecutive meeting, citing slowing inflation and uncertainty in global energy markets.";

async function signIn(page: Page, username: string, password: string, secret?: string) {
  await page.goto("/login");
  await page.getByLabel("نام کاربری").fill(username);
  await page.getByLabel("گذرواژه").fill(password);
  await page.getByRole("button", { name: "ادامه" }).click();
  if (!secret) {
    // First login: 2FA enrolment is forced; read the manual key shown next to the QR code.
    secret = (await page.locator("code").innerText()).trim();
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

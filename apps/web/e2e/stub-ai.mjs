// OpenAI-compatible stub used only by the e2e stack: canned answers, no network, no cost.
import { createServer } from "node:http";

const analysis = {
  title: "بانک مرکزی نرخ بهره را ثابت نگه داشت",
  summary: "بانک مرکزی برای سومین نشست پیاپی نرخ بهره را بدون تغییر گذاشت.",
  category: "economy",
  region: "اروپا",
  risk: "low",
  zone: "green",
  relevance: 80,
  approach: "original_post",
  opportunity: "تحلیل آرام درباره ثبات سیاست پولی",
  sentiment: 0.1,
};

const review = {
  score: 88,
  issues: [
    {
      type: "tone",
      quote: "",
      reason: "لحن مناسب است؛ قلاب می‌تواند قوی‌تر باشد.",
      red_line: "",
      suggestion: "",
    },
  ],
  suggested_parts: null,
};

const longTweet = "متن آزمایشی بلند ".repeat(20).trim(); // > 280 chars on purpose
const variants = {
  variants: [
    {
      angle: "ثبات و پیش‌بینی‌پذیری",
      parts: ["ثبات در سیاست پولی، پیش‌بینی‌پذیری بازار را تقویت می‌کند."],
    },
    {
      angle: "نگاه تمدنی",
      parts: ["اقتصادهای پایدار بر صبر و دقت بنا می‌شوند، نه واکنش لحظه‌ای."],
    },
    { angle: "نگاه صادرکنندگان", parts: [longTweet] },
  ],
};

createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    const payload = JSON.parse(body || "{}");
    res.setHeader("content-type", "application/json");
    const user = payload.messages?.at(-1)?.content ?? "";
    const answer = user.includes("Items from the period")
      ? "خلاصه آزمایشی: امروز تحولات مهمی در منابع رصد نشد."
      : user.includes("Review this draft")
        ? review
        : user.includes("Analyse this item")
          ? analysis
          : variants;
    const content = typeof answer === "string" ? answer : JSON.stringify(answer);
    res.end(JSON.stringify({ choices: [{ message: { role: "assistant", content } }] }));
  });
}).listen(9099, "0.0.0.0");

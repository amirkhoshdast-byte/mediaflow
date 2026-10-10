// OpenAI-compatible stub used only by the e2e stack: canned answers, no network, no cost.
import { createServer } from "node:http";

const analysis = {
  title: "بانک مرکزی نرخ بهره را ثابت نگه داشت",
  summary: "بانک مرکزی برای سومین نشست پیاپی نرخ بهره را بدون تغییر گذاشت.",
  category: "economy",
  region: "اروپا",
  risk: "low",
  approach: "original_post",
  opportunity: "تحلیل آرام درباره ثبات سیاست پولی",
  sentiment: 0.1,
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

// Deterministic bag-of-words vectors: texts that share words are close, which is all search needs.
function embed(text) {
  const v = new Array(1024).fill(0);
  for (const word of text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
    let h = 2166136261;
    for (const ch of word) h = Math.imul(h ^ ch.codePointAt(0), 16777619) >>> 0;
    v[h % 1024] += 1;
  }
  const norm = Math.hypot(...v) || 1;
  return v.map((x) => x / norm);
}

createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    const payload = JSON.parse(body || "{}");
    res.setHeader("content-type", "application/json");
    if (req.url.endsWith("/embeddings")) {
      const data = payload.input.map((t, index) => ({ index, embedding: embed(t) }));
      return res.end(JSON.stringify({ data }));
    }
    const user = payload.messages?.at(-1)?.content ?? "";
    const content = JSON.stringify(user.includes("Analyse this item") ? analysis : variants);
    res.end(JSON.stringify({ choices: [{ message: { role: "assistant", content } }] }));
  });
}).listen(9099, "0.0.0.0");

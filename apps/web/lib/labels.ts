// Persian UI strings for server-side enums.
export const ROLE_FA: Record<string, string> = {
  owner: "مدیر حساب",
  assistant: "دستیار",
  sysadmin: "مدیر سامانه",
};
export const RISK_FA: Record<string, string> = {
  low: "کم",
  medium: "متوسط",
  high: "زیاد",
  critical: "بحرانی",
};
export const RISK_CLASS: Record<string, string> = {
  low: "border-ok text-ok",
  medium: "border-warn text-warn",
  high: "border-danger text-danger",
  critical: "border-danger bg-danger text-accent-fg",
};
export const STAGE_FA: Record<string, string> = {
  draft: "پیش‌نویس",
  approved: "تأییدشده",
  published: "منتشرشده",
};
export const FORMAT_FA: Record<string, string> = {
  tweet: "توییت",
  thread: "رشته",
  reply: "ریپلای",
  quote: "نقل‌قول",
};
export const LANG_FA: Record<string, string> = { fa: "فارسی", en: "انگلیسی", ar: "عربی" };
export const APPROACH_FA: Record<string, string> = {
  monitor_only: "فقط رصد",
  strategic_silence: "سکوت راهبردی",
  original_post: "پست مستقل",
  reply: "ریپلای",
  quote: "نقل‌قول",
};
export const CATEGORY_FA: Record<string, string> = {
  diplomacy: "دیپلماسی",
  economy: "اقتصاد",
  culture: "فرهنگ",
  science_tech: "علم و فناوری",
  law: "حقوق",
  energy: "انرژی",
  humanitarian: "بشردوستانه",
  media: "رسانه",
  military: "نظامی",
  security: "امنیتی",
  judicial: "قضایی",
  politics: "سیاست",
  international: "بین‌الملل",
  society: "اجتماع",
  information_war: "جنگ روایت",
  other: "سایر",
};
export const PERSONA_FA: Record<string, string> = {
  diplomat: "دیپلمات",
  analyst: "تحلیلگر",
  civilizational_narrator: "روایتگر تمدنی",
};
export const PILLAR_FA: Record<string, string> = {
  civilization_culture: "تمدن و فرهنگ",
  diplomacy_cooperation: "دیپلماسی و همکاری",
  economy_development: "اقتصاد و توسعه",
  science_technology: "علم و فناوری",
  international_law: "حقوق بین‌الملل",
  global_events: "رویدادهای جهانی",
};
export const ERROR_FA: Record<string, string> = {
  invalid_credentials: "نام کاربری یا گذرواژه نادرست است.",
  account_locked: "حساب به‌دلیل تلاش‌های ناموفق قفل شد؛ چند دقیقه بعد دوباره تلاش کنید.",
  invalid_code: "کد دومرحله‌ای نادرست است.",
  invalid_challenge: "نشست ورود منقضی شد؛ دوباره شروع کنید.",
  approval_level_insufficient: "سطح دسترسی شما برای تأیید این ریسک کافی نیست.",
  only_reviewers_may_lower_risk: "کاهش سطح ریسک فقط توسط بازبین مجاز است.",
  no_valid_approval: "تأیید معتبری برای این پیش‌نویس ثبت نشده است.",
  duplicate: "این خبر قبلاً ثبت شده است.",
  high_risk_needs_confirmation: "برای تأیید پیش‌نویس پرریسک باید صراحتاً تأیید کنید.",
  forbidden: "دسترسی مجاز نیست.",
  red_line_exists: "این مورد قبلاً در فهرست خطوط قرمز هست.",
  rss_needs_http_url: "برای RSS آدرس http یا https لازم است.",
  gdelt_needs_query: "برای GDELT عبارت جست‌وجو لازم است.",
  x_needs_username: "نام کاربری X نامعتبر است (فقط حروف انگلیسی، عدد و _ تا ۱۵ نویسه).",
  source_exists: "این منبع قبلاً اضافه شده است.",
  username_taken: "این نام کاربری قبلاً استفاده شده است.",
};
export const faError = (e: unknown): string => {
  const d = (e as { detail?: unknown })?.detail;
  const code = typeof d === "string" ? d : (d as { code?: string })?.code;
  if (code && ERROR_FA[code]) return ERROR_FA[code];
  if (typeof code === "string" && code.startsWith("generation_failed"))
    return "تولید محتوا ناموفق بود؛ تنظیمات ارائه‌دهنده هوش مصنوعی را بررسی کنید.";
  return "خطایی رخ داد. دوباره تلاش کنید.";
};

export const RED_KIND_FA: Record<string, string> = {
  topic: "موضوع",
  phrase: "عبارت",
};

export const ZONE_FA: Record<string, string> = {
  green: "ورود فعال",
  yellow: "با قاب فرهنگی",
  red: "سکوت راهبردی",
  rebuttal: "روایت و پاسخ",
};
export const ZONE_CLASS: Record<string, string> = {
  green: "border-ok text-ok",
  yellow: "border-warn text-warn",
  red: "border-danger text-danger",
  rebuttal: "border-accent text-accent",
};

export const ISSUE_TYPE_FA: Record<string, string> = {
  red_line_phrase: "عبارت خط قرمز",
  red_line_topic: "موضوع خط قرمز",
  office_language: "زبان اداری",
  format: "قالب",
  tone: "لحن",
  fact: "واقعیت و منبع",
  other: "نکته",
};

export const SLOT_FA: Record<string, string> = {
  morning: "گزارش هوش صبح (۸:۰۰)",
  afternoon: "گزارش هوش عصر (۱۶:۰۰)",
  manual: "گزارش دستی",
};

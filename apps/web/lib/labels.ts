// Persian UI strings for server-side enums.
export const ROLE_FA: Record<string, string> = {
  trend_analyst: "تحلیلگر روند",
  media_monitor: "رصدگر رسانه",
  ai_operator: "اپراتور هوش مصنوعی",
  content_lead: "مسئول محتوا",
  narrative_strategist: "راهبر روایت",
  diplomatic_editor: "ویراستار دیپلماتیک",
  president_office: "دفتر رئیس",
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
  tone_review: "بازبینی لحن",
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
  forbidden: "دسترسی مجاز نیست.",
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

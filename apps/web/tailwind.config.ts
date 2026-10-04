import type { Config } from "tailwindcss";

const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        raised: v("raised"),
        line: v("line"),
        fg: v("fg"),
        muted: v("muted"),
        accent: v("accent"),
        "accent-fg": v("accent-fg"),
        ok: v("ok"),
        warn: v("warn"),
        danger: v("danger"),
      },
      fontFamily: {
        sans: ["Vazirmatn", "system-ui", "sans-serif"],
        naskh: ['"Noto Naskh Arabic"', "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;

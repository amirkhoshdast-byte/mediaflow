import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "اتاق فرمان روایت",
  description: "رصد، تحلیل و تولید محتوای دیپلماسی عمومی با تأیید انسانی",
  manifest: "/manifest.webmanifest",
};
export const viewport: Viewport = { themeColor: "#185f8c", width: "device-width", initialScale: 1 };

// Applies the saved/system theme before first paint to avoid a flash.
const themeScript = `try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

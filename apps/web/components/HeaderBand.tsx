"use client";

import Link from "next/link";
import { format } from "date-fns-jalali";
import { faIR } from "date-fns-jalali/locale";
import { useEffect, useState } from "react";
import { ROLE_FA } from "@/lib/labels";
import type { Me, Stats } from "@/lib/types";

const ZONES = [
  { label: "تهران", tz: "Asia/Tehran" },
  { label: "بروکسل", tz: "Europe/Brussels" },
  { label: "نیویورک", tz: "America/New_York" },
];

function Meter({ label, done, target }: { label: string; done: number; target: number | null }) {
  const pct = target ? Math.min(100, Math.round((done / target) * 100)) : 0;
  return (
    <div className="min-w-24 flex-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="tabular-nums">
          {done.toLocaleString("fa-IR")}
          {target ? ` / ${target.toLocaleString("fa-IR")}` : ""}
        </span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-raised"
        role="progressbar"
        aria-label={label}
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={target ?? undefined}
      >
        <div
          className={`h-full rounded-full ${pct >= 100 ? "bg-ok" : "bg-accent"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function HeaderBand({
  me,
  stats,
  onLogout,
}: {
  me: Me;
  stats: Stats | null;
  onLogout: () => void;
}) {
  const [now, setNow] = useState<Date | null>(null);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    setDark(document.documentElement.classList.contains("dark"));
    return () => clearInterval(t);
  }, []);

  function toggleTheme() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
    setDark(next);
  }

  const clock = (tz: string) =>
    now
      ? new Intl.DateTimeFormat("fa-IR", {
          timeZone: tz,
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23",
        }).format(now)
      : "--:--";

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <div>
          <h1 className="text-base font-bold">اتاق فرمان روایت</h1>
          <p className="text-xs text-muted" suppressHydrationWarning>
            {now
              ? `${format(now, "EEEE d MMMM yyyy", { locale: faIR })} · ${new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(now)}`
              : " "}
          </p>
        </div>

        <ul className="flex gap-4" aria-label="ساعت‌ها">
          {ZONES.map((z) => (
            <li key={z.tz} className="text-center">
              <div className="text-sm font-medium tabular-nums" suppressHydrationWarning>
                {clock(z.tz)}
              </div>
              <div className="text-xs text-muted">{z.label}</div>
            </li>
          ))}
        </ul>

        <div className="flex min-w-60 flex-1 gap-4" aria-label="اهداف روزانه">
          <Meter
            label="پست امروز"
            done={stats?.posts.done ?? 0}
            target={stats?.posts.target ?? null}
          />
          <Meter
            label="ریپلای امروز"
            done={stats?.replies.done ?? 0}
            target={stats?.replies.target ?? null}
          />
          <Meter label="سیگنال امروز" done={stats?.signals_today ?? 0} target={null} />
        </div>

        <div className="ms-auto flex items-center gap-2">
          <span className="text-sm">
            {me.display_name} <span className="text-muted">· {ROLE_FA[me.role]}</span>
          </span>
          <Link href="/knowledge" className="btn">
            پایگاه دانش
          </Link>
          {me.permissions.includes("users:manage") && (
            <Link href="/admin" className="btn">
              مدیریت
            </Link>
          )}
          <button className="btn" onClick={toggleTheme} aria-pressed={dark}>
            {dark ? "روشن" : "تیره"}
          </button>
          <button className="btn" onClick={onLogout}>
            خروج
          </button>
        </div>
      </div>
    </header>
  );
}

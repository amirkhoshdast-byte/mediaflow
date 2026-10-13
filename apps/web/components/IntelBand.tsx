"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CATEGORY_FA, ZONE_CLASS, ZONE_FA } from "@/lib/labels";
import type { IntelOverview, Signal } from "@/lib/types";
import { RiskBadge } from "./DraftCard";

const fa = (n: number) => n.toLocaleString("fa-IR");

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="card p-3">
      <div className={`text-2xl font-bold tabular-nums ${tone ?? ""}`}>{fa(value)}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

function Row({ s, onPick }: { s: Signal; onPick: (s: Signal) => void }) {
  return (
    <li className="flex flex-wrap items-center gap-2 border-t border-line py-2 first:border-t-0">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{s.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
          {s.zone && <span className={`badge ${ZONE_CLASS[s.zone]}`}>{ZONE_FA[s.zone]}</span>}
          {s.risk && <RiskBadge risk={s.risk} />}
          {s.category && (
            <span className="badge border-line text-muted">{CATEGORY_FA[s.category]}</span>
          )}
          {s.region && <span className="text-muted">{s.region}</span>}
        </div>
      </div>
      <button className="btn" onClick={() => onPick(s)}>
        تولید محتوا
      </button>
    </li>
  );
}

export function IntelBand({
  onPick,
  refreshKey,
}: {
  onPick: (s: Signal) => void;
  refreshKey: number;
}) {
  const [o, setO] = useState<IntelOverview | null>(null);

  useEffect(() => {
    let live = true;
    const load = () =>
      api<IntelOverview>("/intel/overview")
        .then((d) => live && setO(d))
        .catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [refreshKey]);

  if (!o) return null;

  const attention = [
    ...o.rebuttals,
    ...o.high_risk.filter((h) => !o.rebuttals.some((r) => r.id === h.id)),
  ];
  const relevant = Object.values(o.by_zone).reduce((a, b) => a + b, 0);

  return (
    <section
      aria-label="مرور هوشمند ۲۴ ساعت گذشته"
      className="mx-auto max-w-[1600px] space-y-3 px-4 pt-4"
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="سیگنال مرتبط (۲۴ ساعت)" value={relevant} />
        <Stat label="نیازمند توجه (ریسک زیاد)" value={o.high_risk.length} tone="text-warn" />
        <Stat label="روایت و پاسخ" value={o.by_zone.rebuttal ?? 0} tone="text-accent" />
        <Stat label="منابع فعال" value={o.sources.active} />
      </div>

      {o.sources.failing > 0 && (
        <p role="status" className="text-sm text-warn">
          {fa(o.sources.failing)} منبع در دریافت خطا دارد.{" "}
          <Link href="/sources" className="underline">
            بررسی منابع
          </Link>
        </p>
      )}

      {relevant === 0 ? (
        <p className="card p-3 text-sm text-muted">
          {o.total === 0
            ? "هنوز سیگنالی از منابع نرسیده است. دریافت خودکار هر ۱۵ دقیقه اجرا می‌شود؛ وضعیت هر منبع در صفحه منابع است."
            : `${fa(o.analyzing)} سیگنال در حال تحلیل است.`}
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="card p-3">
            <h2 className="mb-1 text-sm font-bold">مهم‌ترین‌های امروز</h2>
            <ul>
              {o.top.map((s) => (
                <Row key={s.id} s={s} onPick={onPick} />
              ))}
            </ul>
          </div>
          <div className="card p-3">
            <h2 className="mb-1 text-sm font-bold">نیازمند توجه دفتر رئیس</h2>
            {attention.length === 0 ? (
              <p className="text-sm text-muted">مورد پرریسک یا نیازمند پاسخی نیست.</p>
            ) : (
              <ul>
                {attention.map((s) => (
                  <Row key={s.id} s={s} onPick={onPick} />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

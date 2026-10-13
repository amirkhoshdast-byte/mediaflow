"use client";

import { format } from "date-fns-jalali";
import { faIR } from "date-fns-jalali/locale";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RiskBadge } from "@/components/DraftCard";
import { api } from "@/lib/api";
import { CATEGORY_FA, SLOT_FA, STAGE_FA, ZONE_CLASS, ZONE_FA } from "@/lib/labels";
import type { Report, ReportSignal } from "@/lib/types";

const fa = (n: number) => n.toLocaleString("fa-IR");

function List({ title, items, note }: { title: string; items: ReportSignal[]; note?: boolean }) {
  return (
    <section aria-label={title} className="card space-y-1 p-3">
      <h2 className="text-sm font-bold">{title}</h2>
      {items.length === 0 && <p className="text-sm text-muted">موردی نیست.</p>}
      <ul>
        {items.map((s) => (
          <li key={s.id} className="space-y-1 border-t border-line py-2 first:border-t-0">
            <div className="text-sm font-medium">{s.title}</div>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              {s.zone && <span className={`badge ${ZONE_CLASS[s.zone]}`}>{ZONE_FA[s.zone]}</span>}
              {s.risk && <RiskBadge risk={s.risk} />}
              {s.category && (
                <span className="badge border-line text-muted">{CATEGORY_FA[s.category]}</span>
              )}
              {s.region && <span className="text-muted">{s.region}</span>}
            </div>
            {note && s.opportunity && <p className="text-xs text-muted">فرصت: {s.opportunity}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [r, setR] = useState<Report | null>(null);

  useEffect(() => {
    api<Report>(`/reports/${id}`)
      .then(setR)
      .catch(() => router.replace("/reports"));
  }, [id, router]);

  if (!r)
    return (
      <main className="p-8 text-sm text-muted" role="status">
        در حال بارگذاری…
      </main>
    );
  const c = r.content;
  const when = (iso: string) => format(new Date(iso), "d MMMM HH:mm", { locale: faIR });

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">{SLOT_FA[r.slot]}</h1>
          <p className="text-xs text-muted">
            بازه: {when(r.period_start)} تا {when(r.period_end)}
          </p>
        </div>
        <Link href="/reports" className="btn">
          همه گزارش‌ها
        </Link>
      </div>

      <section aria-label="خلاصه" className="card space-y-1 p-3">
        <h2 className="text-sm font-bold">خلاصه</h2>
        {r.brief ? (
          <p className="whitespace-pre-line leading-8">{r.brief}</p>
        ) : (
          <p className="text-sm text-warn">خلاصه‌ی هوش مصنوعی ساخته نشد؛ بخش‌های زیر کامل‌اند.</p>
        )}
      </section>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ["سیگنال مرتبط", c.counts.signals],
          ["پرریسک", c.risks.length],
          ["روایت و پاسخ", c.rebuttals.length],
          ["منابع دارای خطا", c.sources.failing],
        ].map(([label, n]) => (
          <div key={label as string} className="card p-3">
            <div className="text-2xl font-bold tabular-nums">{fa(n as number)}</div>
            <div className="text-xs text-muted">{label}</div>
          </div>
        ))}
      </div>

      <List title="مهم‌ترین‌ها" items={c.top} />
      <div className="grid gap-4 lg:grid-cols-2">
        <List title="ریسک‌های رسانه‌ای" items={c.risks} />
        <List title="روایت و پاسخ" items={c.rebuttals} note />
      </div>
      <List title="فرصت‌های محتوایی" items={c.opportunities} note />

      <section aria-label="صف و اهداف" className="card space-y-2 p-3 text-sm">
        <h2 className="font-bold">صف انتشار و اهداف امروز</h2>
        <div className="flex flex-wrap gap-2">
          {Object.entries(c.pipeline.stages).map(([stage, n]) => (
            <span key={stage} className="badge border-line text-muted">
              {STAGE_FA[stage]}: {fa(n)}
            </span>
          ))}
        </div>
        <p>
          در انتظار تأیید: <strong>{fa(c.pipeline.awaiting_approval)}</strong> · پرریسک باز:{" "}
          <strong>{fa(c.pipeline.high_risk_open)}</strong>
        </p>
        <p className="text-muted">
          پست‌های امروز {fa(c.targets.posts.done)} از {fa(c.targets.posts.target)} · ریپلای‌ها{" "}
          {fa(c.targets.replies.done)} از {fa(c.targets.replies.target)}
        </p>
      </section>
    </main>
  );
}

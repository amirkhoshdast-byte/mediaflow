"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ISSUE_TYPE_FA } from "@/lib/labels";
import type { Draft, ToneReview } from "@/lib/types";
import { RiskBadge } from "./DraftCard";

const fa = (n: number) => n.toLocaleString("fa-IR");

function scoreClass(score: number) {
  return score >= 80
    ? "border-ok text-ok"
    : score >= 60
      ? "border-warn text-warn"
      : "border-danger text-danger";
}

export function ToneReviewPanel({
  draft,
  canApply,
  onApply,
}: {
  draft: Draft;
  canApply: boolean;
  onApply: (parts: string[]) => void;
}) {
  const [review, setReview] = useState<ToneReview | null>(null);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const r = await api<ToneReview>(`/drafts/${draft.id}/review`);
        if (!live) return;
        setReview(r);
        if (r.status === "analyzing") timer = setTimeout(load, 2000);
      } catch {
        if (live) setReview(null);
      }
    };
    load();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [draft.id, draft.updated_at]);

  if (!review) return null;
  const blocking = review.issues.some((i) => i.severity === "high" || i.severity === "critical");

  return (
    <section
      aria-label="بررسی لحن"
      className="space-y-2 rounded-md border border-line bg-raised p-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <strong>بررسی لحن</strong>
        {review.status === "analyzing" && (
          <span role="status" className="text-xs text-muted">
            در حال بررسی…
          </span>
        )}
        {review.score !== null && (
          <span className={`badge ${scoreClass(review.score)}`}>امتیاز {fa(review.score)}</span>
        )}
        {blocking && <span className="badge border-danger text-danger">برخورد با خط قرمز</span>}
      </div>

      {review.status === "failed" && (
        <p className="text-xs text-warn">
          ارزیابی هوش مصنوعی انجام نشد؛ فقط بررسی‌های قطعی نمایش داده می‌شود.
        </p>
      )}
      {review.stale && <p className="text-xs text-warn">متن بعد از این بررسی تغییر کرده است.</p>}
      {review.status !== "analyzing" && review.issues.length === 0 && (
        <p className="text-xs text-muted">مغایرتی پیدا نشد.</p>
      )}

      <ul className="space-y-1.5">
        {review.issues.map((i, n) => (
          <li key={n} className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="badge border-line text-muted">{ISSUE_TYPE_FA[i.type]}</span>
              {i.severity && <RiskBadge risk={i.severity} />}
              {i.quote && <mark className="rounded bg-warn/20 px-1">{i.quote}</mark>}
            </div>
            <p className="leading-6">{i.reason}</p>
            {i.suggestion && <p className="text-xs text-muted">پیشنهاد: {i.suggestion}</p>}
          </li>
        ))}
      </ul>

      {review.suggested_parts && (
        <div className="space-y-1 border-t border-line pt-2">
          <div className="text-xs font-bold">نسخه پیشنهادی</div>
          {review.suggested_parts.map((p, n) => (
            <p key={n} className="leading-6">
              {p}
            </p>
          ))}
          {canApply && (
            <button className="btn" onClick={() => onApply(review.suggested_parts!)}>
              اعمال پیشنهاد
            </button>
          )}
        </div>
      )}
    </section>
  );
}

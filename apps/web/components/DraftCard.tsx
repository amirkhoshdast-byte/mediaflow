"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FORMAT_FA, LANG_FA, RISK_CLASS, RISK_FA, STAGE_FA, faError } from "@/lib/labels";
import type { Draft, Me, Meta, Risk, Stage } from "@/lib/types";

const fa = (n: number) => n.toLocaleString("fa-IR");

export function RiskBadge({ risk }: { risk: string }) {
  return <span className={`badge ${RISK_CLASS[risk]}`}>ریسک {RISK_FA[risk]}</span>;
}

export function DraftCard({
  draft,
  me,
  meta,
  onChange,
  onError,
  showStage = false,
}: {
  draft: Draft;
  me: Me;
  meta: Meta;
  onChange: () => void;
  onError: (m: string) => void;
  showStage?: boolean;
}) {
  const can = (p: string) => me.permissions.includes(p);
  const [parts, setParts] = useState(draft.parts);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  useEffect(() => setParts(draft.parts), [draft.parts, draft.updated_at]);

  const editable = can("draft:edit") && draft.stage !== "published";
  const approveLevel =
    draft.risk === "high" || draft.risk === "critical"
      ? "approve:high_critical"
      : "approve:low_medium";

  async function call(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      onChange();
    } catch (e) {
      onError(faError(e));
    } finally {
      setBusy(false);
    }
  }
  const save = () => {
    if (JSON.stringify(parts) !== JSON.stringify(draft.parts))
      call(() => api(`/drafts/${draft.id}`, { method: "PATCH", body: { parts } }));
  };
  const move = (to: Stage, note?: string) =>
    call(() => api(`/drafts/${draft.id}/transition`, { body: { to, note } }));

  async function copy() {
    try {
      await navigator.clipboard.writeText(parts.join("\n\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      onError("کپی انجام نشد.");
    }
  }

  return (
    <article className="card space-y-2 p-3" aria-label={draft.angle ?? "پیش‌نویس"}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="badge border-line text-muted">
          {FORMAT_FA[draft.format]} · {LANG_FA[draft.language]}
        </span>
        <RiskBadge risk={draft.risk} />
        {showStage && (
          <span className="badge border-accent text-accent">{STAGE_FA[draft.stage]}</span>
        )}
        {draft.angle && <span className="text-muted">{draft.angle}</span>}
      </div>

      {parts.map((text, i) => {
        const n = text.length;
        const over = n > meta.limits.hard;
        const near = n > meta.limits.soft;
        return (
          <div key={i}>
            <textarea
              className={`input min-h-24 resize-y ${over ? "border-danger" : ""}`}
              dir={draft.language === "en" ? "ltr" : "rtl"}
              lang={draft.language}
              value={text}
              readOnly={!editable}
              aria-label={parts.length > 1 ? `بخش ${fa(i + 1)}` : "متن"}
              aria-invalid={over}
              onChange={(e) => setParts(parts.map((p, j) => (j === i ? e.target.value : p)))}
              onBlur={save}
            />
            <div
              className={`mt-0.5 text-xs tabular-nums ${over ? "font-bold text-danger" : near ? "text-warn" : "text-muted"}`}
            >
              {fa(n)} / {fa(meta.limits.hard)}
              {over && " — بیش از حد مجاز"}
            </div>
          </div>
        );
      })}

      <div className="flex flex-wrap gap-1 text-xs">
        {draft.checks.too_many_hashtags && (
          <span className="badge border-warn text-warn">بیش از یک هشتگ</span>
        )}
        {draft.checks.has_emoji && <span className="badge border-warn text-warn">شامل ایموجی</span>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {editable && (
          <select
            aria-label="سطح ریسک"
            className="input !w-auto !py-1"
            value={draft.risk}
            disabled={busy}
            onChange={(e) =>
              call(() =>
                api(`/drafts/${draft.id}`, {
                  method: "PATCH",
                  body: { risk: e.target.value as Risk },
                }),
              )
            }
          >
            {(["low", "medium", "high", "critical"] as Risk[]).map((r) => (
              <option key={r} value={r}>
                ریسک {RISK_FA[r]}
              </option>
            ))}
          </select>
        )}
        <button className="btn" onClick={copy}>
          {copied ? "کپی شد" : "کپی"}
        </button>

        {draft.stage === "draft" && can("draft:submit") && (
          <button className="btn btn-primary" disabled={busy} onClick={() => move("tone_review")}>
            ارسال به بازبینی
          </button>
        )}
        {draft.stage === "tone_review" && can(approveLevel) && (
          <>
            <button className="btn btn-primary" disabled={busy} onClick={() => move("approved")}>
              تأیید
            </button>
            <button
              className="btn btn-danger"
              disabled={busy}
              onClick={() => move("draft", window.prompt("دلیل بازگشت به پیش‌نویس:") ?? undefined)}
            >
              بازگشت
            </button>
          </>
        )}
        {draft.stage === "tone_review" && !can(approveLevel) && (
          <span className="text-xs text-muted">
            {approveLevel === "approve:high_critical"
              ? "در انتظار تأیید دفتر رئیس"
              : "در انتظار ویراستار دیپلماتیک"}
          </span>
        )}
        {draft.stage === "approved" && can("draft:publish") && (
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() =>
              window.confirm("پس از انتشار دستی در X، ثبت انتشار انجام شود؟") && move("published")
            }
          >
            ثبت انتشار
          </button>
        )}
      </div>
    </article>
  );
}

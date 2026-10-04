"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { APPROACH_FA, CATEGORY_FA, faError } from "@/lib/labels";
import type { Me, Signal } from "@/lib/types";
import { RiskBadge } from "./DraftCard";

export function MonitorColumn({
  me,
  signals,
  selectedId,
  onSelect,
  onChange,
  onError,
}: {
  me: Me;
  signals: Signal[];
  selectedId: string | null;
  onSelect: (s: Signal) => void;
  onChange: () => void;
  onError: (m: string) => void;
}) {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const canAdd = me.permissions.includes("signal:add");

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/signals", { body: { text, url: url || null } });
      setText("");
      setUrl("");
      onChange();
    } catch (err) {
      onError(faError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="mon-h" className="space-y-3">
      <h2 id="mon-h" className="text-sm font-bold">
        رصد
      </h2>

      {canAdd && (
        <form onSubmit={add} className="card space-y-2 p-3">
          <label className="block text-sm">
            متن خبر یا توییت
            <textarea
              className="input mt-1 min-h-24"
              value={text}
              minLength={20}
              required
              onChange={(e) => setText(e.target.value)}
              placeholder="خبر را اینجا بچسبانید…"
            />
          </label>
          <input
            className="input"
            dir="ltr"
            placeholder="پیوند (اختیاری)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button className="btn btn-primary w-full" disabled={busy || text.trim().length < 20}>
            {busy ? "در حال ثبت…" : "افزودن و تحلیل"}
          </button>
        </form>
      )}

      <ul className="space-y-2">
        {signals.length === 0 && <li className="text-sm text-muted">هنوز سیگنالی ثبت نشده است.</li>}
        {signals.map((s) => (
          <li key={s.id}>
            <article
              className={`card space-y-1.5 p-3 ${selectedId === s.id ? "border-accent" : ""}`}
            >
              {s.status === "analyzing" && (
                <p className="text-sm text-muted" role="status">
                  در حال تحلیل…
                </p>
              )}
              {s.status === "failed" && (
                <div className="space-y-1">
                  <p className="text-sm text-danger">تحلیل ناموفق بود.</p>
                  <p className="line-clamp-2 text-xs text-muted" dir="ltr">
                    {s.text}
                  </p>
                  {canAdd && (
                    <button
                      className="btn"
                      onClick={() => api(`/signals/${s.id}/retry`, { body: {} }).then(onChange)}
                    >
                      تلاش دوباره
                    </button>
                  )}
                </div>
              )}
              {s.status === "ready" && (
                <>
                  <h3 className="text-sm font-bold leading-6">{s.title}</h3>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    {s.risk && <RiskBadge risk={s.risk} />}
                    {s.approach && (
                      <span className="badge border-accent text-accent">
                        {APPROACH_FA[s.approach]}
                      </span>
                    )}
                    {s.category && (
                      <span className="badge border-line text-muted">
                        {CATEGORY_FA[s.category]}
                      </span>
                    )}
                    {s.region && <span className="badge border-line text-muted">{s.region}</span>}
                  </div>
                  <p className="text-sm leading-6">{s.summary}</p>
                  {s.opportunity && <p className="text-xs text-muted">فرصت: {s.opportunity}</p>}
                  <button className="btn" onClick={() => onSelect(s)}>
                    {selectedId === s.id ? "انتخاب‌شده در استودیو" : "تولید محتوا"}
                  </button>
                </>
              )}
            </article>
          </li>
        ))}
      </ul>
    </section>
  );
}

"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { APPROACH_FA, FORMAT_FA, LANG_FA, PERSONA_FA, PILLAR_FA, faError } from "@/lib/labels";
import type { Draft, Me, Meta, Signal } from "@/lib/types";
import { DraftCard } from "./DraftCard";

export function StudioColumn({
  me,
  meta,
  signal,
  onClearSignal,
  drafts,
  onGenerated,
  onChange,
  onError,
}: {
  me: Me;
  meta: Meta;
  signal: Signal | null;
  onClearSignal: () => void;
  drafts: Draft[];
  onGenerated: (group: string) => void;
  onChange: () => void;
  onError: (m: string) => void;
}) {
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState("tweet");
  const [language, setLanguage] = useState("fa");
  const [persona, setPersona] = useState(meta.personas[0]);
  const [pillar, setPillar] = useState(meta.pillars[0]);
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const canEdit = me.permissions.includes("draft:edit");
  const silent =
    signal && (signal.approach === "monitor_only" || signal.approach === "strategic_silence");

  async function generate() {
    setBusy(true);
    try {
      const out = await api<Draft[]>("/studio/generate", {
        body: {
          signal_id: signal?.id ?? null,
          topic: signal ? null : topic,
          format,
          language,
          persona,
          pillar,
          instructions,
        },
      });
      onGenerated(out[0].generation_group!);
      onChange();
    } catch (e) {
      onError(faError(e));
    } finally {
      setBusy(false);
    }
  }

  const sel = (
    label: string,
    value: string,
    set: (v: string) => void,
    opts: [string, string][],
  ) => (
    <label className="block text-xs text-muted">
      {label}
      <select className="input mt-1 !py-1.5" value={value} onChange={(e) => set(e.target.value)}>
        {opts.map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <section aria-labelledby="stu-h" className="space-y-3">
      <h2 id="stu-h" className="text-sm font-bold">
        استودیوی محتوا
      </h2>

      {!canEdit ? (
        <p className="card p-3 text-sm text-muted">نقش شما به استودیو دسترسی ویرایش ندارد.</p>
      ) : (
        <div className="card space-y-3 p-3">
          {signal ? (
            <div className="rounded-md bg-raised p-2 text-sm">
              <div className="flex items-start justify-between gap-2">
                <strong className="leading-6">{signal.title}</strong>
                <button className="btn !px-2 !py-0.5 text-xs" onClick={onClearSignal}>
                  حذف
                </button>
              </div>
              {silent && (
                <p role="alert" className="mt-1 text-xs text-warn">
                  رویکرد پیشنهادی این سیگنال «{APPROACH_FA[signal.approach!]}» است؛ تولید محتوا ممکن
                  است مناسب نباشد.
                </p>
              )}
            </div>
          ) : (
            <label className="block text-sm">
              موضوع
              <textarea
                className="input mt-1 min-h-20"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="موضوع را بنویسید یا از ستون رصد یک سیگنال انتخاب کنید"
              />
            </label>
          )}
          <div className="grid grid-cols-2 gap-2">
            {sel("قالب", format, setFormat, Object.entries(FORMAT_FA))}
            {sel(
              "زبان",
              language,
              setLanguage,
              meta.languages.map((l) => [l, LANG_FA[l]]),
            )}
            {sel(
              "پرسونا",
              persona,
              setPersona,
              meta.personas.map((p) => [p, PERSONA_FA[p]]),
            )}
            {sel(
              "ستون محتوایی",
              pillar,
              setPillar,
              meta.pillars.map((p) => [p, PILLAR_FA[p]]),
            )}
          </div>
          <input
            className="input"
            placeholder="راهنمای اضافه برای نویسنده (اختیاری)"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
          <button
            className="btn btn-primary w-full"
            disabled={busy || (!signal && topic.trim().length < 3)}
            onClick={generate}
          >
            {busy ? "در حال تولید سه پیشنهاد…" : "تولید سه پیشنهاد"}
          </button>
          {busy && (
            <div role="status" className="h-1 overflow-hidden rounded bg-raised">
              <div className="h-full w-1/3 animate-pulse bg-accent" />
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        {drafts.map((d) => (
          <DraftCard
            key={d.id}
            draft={d}
            me={me}
            meta={meta}
            onChange={onChange}
            onError={onError}
            showStage
          />
        ))}
      </div>
    </section>
  );
}

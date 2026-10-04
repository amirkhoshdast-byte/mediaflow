"use client";

import { STAGE_FA } from "@/lib/labels";
import type { Draft, Me, Meta, Stage } from "@/lib/types";
import { DraftCard } from "./DraftCard";

const STAGES: Stage[] = ["draft", "tone_review", "approved", "published"];

export function PipelineColumn({
  me,
  meta,
  drafts,
  onChange,
  onError,
}: {
  me: Me;
  meta: Meta;
  drafts: Draft[];
  onChange: () => void;
  onError: (m: string) => void;
}) {
  return (
    <section aria-labelledby="pipe-h" className="space-y-4">
      <h2 id="pipe-h" className="text-sm font-bold">
        صف انتشار
      </h2>
      {STAGES.map((st) => {
        const items = drafts.filter((d) => d.stage === st);
        return (
          <div key={st} className="space-y-2">
            <h3 className="flex items-center gap-2 text-xs font-bold text-muted">
              {STAGE_FA[st]}
              <span className="badge border-line">{items.length.toLocaleString("fa-IR")}</span>
            </h3>
            {items.map((d) => (
              <DraftCard
                key={d.id}
                draft={d}
                me={me}
                meta={meta}
                onChange={onChange}
                onError={onError}
              />
            ))}
          </div>
        );
      })}
    </section>
  );
}

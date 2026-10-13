"use client";

import { useState } from "react";
import { STAGE_FA } from "@/lib/labels";
import type { Draft, Me, Meta, Stage } from "@/lib/types";
import { DraftCard } from "./DraftCard";

const STAGES: Stage[] = ["draft", "approved", "published"];

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
  const [tab, setTab] = useState<"all" | "high">("all");
  const isHigh = (d: Draft) => d.risk === "high" || d.risk === "critical";
  const highOpen = drafts.filter((d) => isHigh(d) && d.stage !== "published").length;
  const shown =
    tab === "high" ? drafts.filter((d) => isHigh(d) && d.stage !== "published") : drafts;

  return (
    <section aria-labelledby="pipe-h" className="space-y-4">
      <h2 id="pipe-h" className="text-sm font-bold">
        صف انتشار
      </h2>
      <div role="tablist" aria-label="فیلتر صف" className="flex gap-2">
        <button
          role="tab"
          aria-selected={tab === "all"}
          className={`btn ${tab === "all" ? "btn-primary" : ""}`}
          onClick={() => setTab("all")}
        >
          همه
        </button>
        <button
          role="tab"
          aria-selected={tab === "high"}
          className={`btn ${tab === "high" ? "btn-primary" : highOpen ? "border-danger text-danger" : ""}`}
          onClick={() => setTab("high")}
        >
          ⚠ پرریسک ({highOpen.toLocaleString("fa-IR")})
        </button>
      </div>
      {STAGES.map((st) => {
        const items = shown.filter((d) => d.stage === st);
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

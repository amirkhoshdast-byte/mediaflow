"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HeaderBand } from "@/components/HeaderBand";
import { MonitorColumn } from "@/components/MonitorColumn";
import { PipelineColumn } from "@/components/PipelineColumn";
import { StudioColumn } from "@/components/StudioColumn";
import { api, ApiError } from "@/lib/api";
import type { Draft, Me, Meta, Signal, Stats } from "@/lib/types";

type Tab = "monitor" | "studio" | "pipeline";
const TABS: [Tab, string][] = [
  ["monitor", "رصد"],
  ["studio", "استودیو"],
  ["pipeline", "صف انتشار"],
];

export default function Dashboard() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [picked, setPicked] = useState<Signal | null>(null);
  const [group, setGroup] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("monitor");
  const [toast, setToast] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, d, st] = await Promise.all([
        api<Signal[]>("/signals"),
        api<Draft[]>("/drafts"),
        api<Stats>("/stats/today"),
      ]);
      setSignals(s);
      setDrafts(d);
      setStats(st);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    (async () => {
      try {
        const [m, mt] = await Promise.all([api<Me>("/auth/me"), api<Meta>("/meta")]);
        setMe(m);
        setMeta(mt);
        refresh();
      } catch {
        router.replace("/login");
      }
    })();
  }, [router, refresh]);

  const analyzing = signals.some((s) => s.status === "analyzing");
  useEffect(() => {
    if (!me) return;
    const t = setInterval(refresh, analyzing ? 2000 : 15000);
    return () => clearInterval(t);
  }, [me, analyzing, refresh]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  const studioDrafts = useMemo(
    () => drafts.filter((d) => group && d.generation_group === group),
    [drafts, group],
  );

  if (!me || !meta)
    return (
      <main className="p-8 text-sm text-muted" role="status">
        در حال بارگذاری…
      </main>
    );

  async function logout() {
    await api("/auth/logout", { body: {} }).catch(() => {});
    router.replace("/login");
  }
  const pick = (s: Signal) => {
    setPicked(s);
    setGroup(null);
    setTab("studio");
  };
  const generated = (g: string) => setGroup(g);

  const monitor = (
    <MonitorColumn
      me={me}
      signals={signals}
      selectedId={picked?.id ?? null}
      onSelect={pick}
      onChange={refresh}
      onError={setToast}
    />
  );
  const studio = (
    <StudioColumn
      me={me}
      meta={meta}
      signal={picked}
      onClearSignal={() => setPicked(null)}
      drafts={studioDrafts}
      onGenerated={generated}
      onChange={refresh}
      onError={setToast}
    />
  );
  const pipeline = (
    <PipelineColumn me={me} meta={meta} drafts={drafts} onChange={refresh} onError={setToast} />
  );

  return (
    <>
      <HeaderBand me={me} stats={stats} onLogout={logout} />
      <nav
        className="sticky top-0 z-10 flex border-b border-line bg-surface lg:hidden"
        aria-label="بخش‌ها"
      >
        {TABS.map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            aria-current={tab === k}
            className={`flex-1 py-2.5 text-sm font-medium ${tab === k ? "border-b-2 border-accent text-accent" : "text-muted"}`}
          >
            {label}
          </button>
        ))}
      </nav>
      <main className="mx-auto max-w-[1600px] px-4 py-4">
        <div className="hidden gap-4 lg:grid lg:grid-cols-3">
          {[monitor, studio, pipeline].map((c, i) => (
            <div key={i}>{c}</div>
          ))}
        </div>
        <div className="lg:hidden">
          {tab === "monitor" ? monitor : tab === "studio" ? studio : pipeline}
        </div>
      </main>
      {toast && (
        <div
          role="alert"
          className="fixed inset-x-4 bottom-4 z-20 mx-auto max-w-md rounded-md border border-danger bg-surface p-3 text-sm text-danger shadow-lg"
        >
          {toast}
        </div>
      )}
    </>
  );
}

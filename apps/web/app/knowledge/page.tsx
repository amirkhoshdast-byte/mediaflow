"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DOC_STATUS_FA, DOC_TYPE_FA, SENSITIVITY_FA, faError } from "@/lib/labels";
import type { KbDoc, KbHit, Me } from "@/lib/types";

const fa = (n: number) => n.toLocaleString("fa-IR");

export default function Knowledge() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [hits, setHits] = useState<KbHit[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canManage = !!me?.permissions.includes("kb:manage");

  const load = useCallback(async () => {
    try {
      setDocs(await api<KbDoc[]>("/knowledge/docs"));
    } catch {
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"));
    load();
  }, [load, router]);

  // Embedding runs in the worker; keep refreshing while anything is still processing.
  const processing = docs.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [processing, load]);

  async function run(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(faError(e));
    }
  }

  function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    run(async () => {
      await api("/knowledge/docs", { form: f });
      form.reset();
    }).finally(() => setBusy(false));
  }

  async function search(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const query = String(new FormData(e.currentTarget).get("query")).trim();
    setError("");
    try {
      setHits(await api<KbHit[]>("/knowledge/search", { body: { query, limit: 5 } }));
    } catch (err) {
      setHits(null);
      setError(faError(err));
    }
  }

  const patch = (id: string, body: object) =>
    run(() => api(`/knowledge/docs/${id}`, { method: "PATCH", body }));

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">پایگاه دانش</h1>
        <Link href="/" className="btn">
          بازگشت
        </Link>
      </div>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      <form onSubmit={search} className="card flex gap-2 p-3" role="search">
        <input
          name="query"
          required
          minLength={2}
          className="input"
          placeholder="جست‌وجوی معنایی در اسناد…"
          aria-label="جست‌وجو"
        />
        <button className="btn btn-primary">جست‌وجو</button>
      </form>

      {hits && (
        <section aria-label="نتایج جست‌وجو" className="space-y-2">
          {hits.length === 0 && <p className="text-sm text-muted">نتیجه‌ای پیدا نشد.</p>}
          {hits.map((h, i) => (
            <article key={i} className="card space-y-1 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <strong className="text-sm">{h.title}</strong>
                <span className="badge border-line text-muted">{DOC_TYPE_FA[h.doc_type]}</span>
                {h.sensitivity === "sensitive" && (
                  <span className="badge border-warn text-warn">حساس</span>
                )}
                <span className="ms-auto text-muted tabular-nums">
                  شباهت {fa(Math.round(h.score * 100))}٪
                </span>
              </div>
              <p className="leading-7">{h.text}</p>
            </article>
          ))}
        </section>
      )}

      {canManage && (
        <form onSubmit={upload} className="card grid gap-2 p-3 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            فایل (txt، md، pdf یا docx — حداکثر ۱۰ مگابایت)
            <input
              name="file"
              type="file"
              required
              accept=".txt,.md,.pdf,.docx"
              className="input mt-1"
            />
          </label>
          <input name="title" placeholder="عنوان (اختیاری)" className="input" />
          <select name="doc_type" className="input" defaultValue="identity" aria-label="نوع سند">
            {Object.entries(DOC_TYPE_FA).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select
            name="sensitivity"
            className="input sm:col-span-2"
            defaultValue="normal"
            aria-label="طبقه حساسیت"
          >
            {Object.entries(SENSITIVITY_FA).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <button className="btn btn-primary sm:col-span-2" disabled={busy}>
            {busy ? "در حال بارگذاری…" : "بارگذاری سند"}
          </button>
        </form>
      )}

      <ul className="space-y-2" aria-label="اسناد">
        {docs.length === 0 && <li className="text-sm text-muted">هنوز سندی بارگذاری نشده است.</li>}
        {docs.map((d) => (
          <li key={d.id} className="card space-y-2 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{d.title}</span>
              <span className="badge border-line text-muted">{DOC_TYPE_FA[d.doc_type]}</span>
              {d.sensitivity === "sensitive" && (
                <span className="badge border-warn text-warn">حساس</span>
              )}
              <span
                className={`badge ${d.status === "ready" ? "border-accent text-accent" : d.status === "failed" ? "border-danger text-danger" : "border-line text-muted"}`}
                role={d.status === "processing" ? "status" : undefined}
              >
                {DOC_STATUS_FA[d.status]}
              </span>
              <span className="text-xs text-muted">{fa(d.chunks)} بخش</span>
            </div>
            {d.status === "failed" && d.error && (
              <p className="text-xs text-danger" dir="ltr">
                {d.error}
              </p>
            )}
            {canManage && (
              <div className="flex flex-wrap items-center gap-2">
                <select
                  aria-label="طبقه حساسیت"
                  className="input !w-auto !py-1"
                  value={d.sensitivity}
                  onChange={(e) => patch(d.id, { sensitivity: e.target.value })}
                >
                  {Object.entries(SENSITIVITY_FA).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                {d.status === "failed" && (
                  <button
                    className="btn"
                    onClick={() => run(() => api(`/knowledge/docs/${d.id}/retry`, { body: {} }))}
                  >
                    تلاش دوباره
                  </button>
                )}
                <button
                  className="btn btn-danger ms-auto"
                  onClick={() =>
                    window.confirm(`سند «${d.title}» حذف شود؟`) &&
                    run(() => api(`/knowledge/docs/${d.id}`, { method: "DELETE" }))
                  }
                >
                  حذف
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}

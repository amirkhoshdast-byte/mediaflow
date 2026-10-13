"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RED_KIND_FA, RISK_CLASS, RISK_FA, faError } from "@/lib/labels";
import type { Me, RedLine, Risk } from "@/lib/types";

const RISKS: Risk[] = ["low", "medium", "high", "critical"];

export default function RedLines() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<RedLine[]>([]);
  const [error, setError] = useState("");
  const canManage = !!me?.permissions.includes("redline:manage");

  const load = useCallback(async () => {
    try {
      setRows(await api<RedLine[]>("/redlines"));
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

  async function run(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(faError(e));
    }
  }

  function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    run(async () => {
      await api("/redlines", { body: { ...f, description: f.description || null } });
      form.reset();
    });
  }

  const patch = (id: string, body: object) =>
    run(() => api(`/redlines/${id}`, { method: "PATCH", body }));

  const severitySelect = (value: Risk, onChange: (r: Risk) => void, name?: string) => (
    <select
      name={name}
      aria-label="شدت"
      className="input !w-auto !py-1"
      value={name ? undefined : value}
      defaultValue={name ? "high" : undefined}
      onChange={(e) => onChange(e.target.value as Risk)}
    >
      {RISKS.map((r) => (
        <option key={r} value={r}>
          شدت {RISK_FA[r]}
        </option>
      ))}
    </select>
  );

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">خطوط قرمز</h1>
        <Link href="/" className="btn">
          بازگشت
        </Link>
      </div>
      <p className="text-sm text-muted">
        هر پیش‌نویسی که با یکی از این موارد برخورد کند در بازبینی برجسته می‌شود و سطح ریسکش دست‌کم
        به شدت همان مورد می‌رسد. فهرست اولیه از راهنمای صدا آمده و تا تأیید دفتر رئیس پیش‌نویس است.
      </p>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {canManage && (
        <form onSubmit={create} className="card grid gap-2 p-3 sm:grid-cols-2">
          <select name="kind" className="input" defaultValue="topic" aria-label="نوع">
            {Object.entries(RED_KIND_FA).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          {severitySelect("high", () => {}, "severity")}
          <input
            name="pattern"
            required
            minLength={2}
            maxLength={300}
            placeholder="موضوع یا عبارت"
            className="input sm:col-span-2"
          />
          <input
            name="description"
            maxLength={500}
            placeholder="توضیح (اختیاری)"
            className="input sm:col-span-2"
          />
          <button className="btn btn-primary sm:col-span-2">افزودن</button>
        </form>
      )}

      {(["topic", "phrase"] as const).map((kind) => (
        <section key={kind} aria-label={RED_KIND_FA[kind]} className="space-y-2">
          <h2 className="text-sm font-bold">{kind === "topic" ? "موضوع‌ها" : "عبارت‌ها"}</h2>
          <ul className="space-y-2">
            {rows
              .filter((r) => r.kind === kind)
              .map((r) => (
                <li
                  key={r.id}
                  className={`card flex flex-wrap items-center gap-2 p-3 text-sm ${r.active ? "" : "opacity-60"}`}
                >
                  <span className="font-medium">{r.pattern}</span>
                  <span className={`badge ${RISK_CLASS[r.severity]}`}>
                    شدت {RISK_FA[r.severity]}
                  </span>
                  {!r.active && <span className="badge border-line text-muted">غیرفعال</span>}
                  {r.description && (
                    <span className="basis-full text-xs text-muted">{r.description}</span>
                  )}
                  {canManage && (
                    <span className="ms-auto flex flex-wrap items-center gap-2">
                      {severitySelect(r.severity, (s) => patch(r.id, { severity: s }))}
                      <button className="btn" onClick={() => patch(r.id, { active: !r.active })}>
                        {r.active ? "غیرفعال" : "فعال‌سازی"}
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={() =>
                          window.confirm(`«${r.pattern}» حذف شود؟`) &&
                          run(() => api(`/redlines/${r.id}`, { method: "DELETE" }))
                        }
                      >
                        حذف
                      </button>
                    </span>
                  )}
                </li>
              ))}
          </ul>
        </section>
      ))}
    </main>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { faError } from "@/lib/labels";
import type { Me, Source } from "@/lib/types";

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";

export default function Sources() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<Source[]>([]);
  const [type, setType] = useState<"rss" | "gdelt">("rss");
  const [error, setError] = useState("");
  const canManage = !!me?.permissions.includes("sources:manage");

  const load = useCallback(async () => {
    try {
      setRows(await api<Source[]>("/sources"));
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
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    run(async () => {
      await api("/sources", {
        body: {
          type,
          name: f.name,
          language: f.language,
          ...(type === "rss" ? { url: f.target } : { query: f.target }),
        },
      });
      form.reset();
    });
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">منابع رصد</h1>
        <Link href="/" className="btn">
          بازگشت
        </Link>
      </div>
      <p className="text-sm text-muted">
        فقط رسانه‌ها و منابع عمومی خوانده می‌شوند، هر ۱۵ دقیقه. رویترز و AP خوراک عمومی ندارند و از
        طریق GDELT رصد می‌شوند. خطای هر منبع همین‌جا دیده می‌شود.
      </p>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {canManage && (
        <form onSubmit={create} className="card grid gap-2 p-3 sm:grid-cols-2">
          <select
            className="input"
            aria-label="نوع منبع"
            value={type}
            onChange={(e) => setType(e.target.value as "rss" | "gdelt")}
          >
            <option value="rss">RSS</option>
            <option value="gdelt">GDELT (عبارت جست‌وجو)</option>
          </select>
          <input name="name" required minLength={2} placeholder="نام منبع" className="input" />
          <input
            name="target"
            required
            dir="ltr"
            placeholder={type === "rss" ? "https://example.com/rss.xml" : "Iran domain:reuters.com"}
            className="input sm:col-span-2"
          />
          <select name="language" className="input" defaultValue="en" aria-label="زبان">
            <option value="en">English</option>
            <option value="fa">فارسی</option>
            <option value="ar">العربية</option>
          </select>
          <button className="btn btn-primary">افزودن منبع</button>
        </form>
      )}

      <ul className="space-y-2" aria-label="منابع">
        {rows.map((s) => (
          <li key={s.id} className={`card space-y-1 p-3 text-sm ${s.active ? "" : "opacity-60"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{s.name}</span>
              <span className="badge border-line text-muted">
                {s.type === "rss" ? "RSS" : "GDELT"}
              </span>
              {!s.active && <span className="badge border-line text-muted">غیرفعال</span>}
              <span className="text-xs text-muted">آخرین دریافت: {when(s.last_fetched_at)}</span>
              {canManage && (
                <span className="ms-auto flex gap-2">
                  <button
                    className="btn"
                    onClick={() => run(() => api(`/sources/${s.id}/fetch`, { body: {} }))}
                  >
                    دریافت همین حالا
                  </button>
                  <button
                    className="btn"
                    onClick={() =>
                      run(() =>
                        api(`/sources/${s.id}`, { method: "PATCH", body: { active: !s.active } }),
                      )
                    }
                  >
                    {s.active ? "غیرفعال" : "فعال‌سازی"}
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() =>
                      window.confirm(`منبع «${s.name}» حذف شود؟`) &&
                      run(() => api(`/sources/${s.id}`, { method: "DELETE" }))
                    }
                  >
                    حذف
                  </button>
                </span>
              )}
            </div>
            {s.last_error && (
              <p className="text-xs text-danger" dir="ltr">
                {s.last_error}
              </p>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}

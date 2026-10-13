"use client";

import { format } from "date-fns-jalali";
import { faIR } from "date-fns-jalali/locale";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SLOT_FA, faError } from "@/lib/labels";
import type { Me, ReportSummary } from "@/lib/types";

const fa = (n: number) => n.toLocaleString("fa-IR");

export default function Reports() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<ReportSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api<ReportSummary[]>("/reports"));
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

  async function generate() {
    setBusy(true);
    setError("");
    try {
      const r = await api<ReportSummary>("/reports/generate", { body: {} });
      router.push(`/reports/${r.id}`);
    } catch (e) {
      setError(faError(e));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">گزارش‌های هوش</h1>
        <Link href="/" className="btn">
          بازگشت
        </Link>
      </div>
      <p className="text-sm text-muted">
        هر روز ساعت ۸ صبح و ۱۶ (به وقت تهران) خودکار ساخته و برای تیم اعلان می‌شود.
      </p>
      {me?.permissions.includes("report:run") && (
        <button className="btn btn-primary" onClick={generate} disabled={busy}>
          {busy ? "در حال ساخت گزارش…" : "ساخت گزارش همین حالا (۱۲ ساعت گذشته)"}
        </button>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <ul className="space-y-2" aria-label="گزارش‌ها">
        {rows.length === 0 && <li className="text-sm text-muted">هنوز گزارشی ساخته نشده است.</li>}
        {rows.map((r) => (
          <li key={r.id}>
            <Link
              href={`/reports/${r.id}`}
              className="card flex flex-wrap items-center gap-2 p-3 text-sm hover:bg-raised"
            >
              <span className="font-medium">{SLOT_FA[r.slot]}</span>
              <span className="text-muted">
                {format(new Date(r.created_at), "EEEE d MMMM", { locale: faIR })}
              </span>
              <span className="badge ms-auto border-line text-muted">{fa(r.signals)} سیگنال</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

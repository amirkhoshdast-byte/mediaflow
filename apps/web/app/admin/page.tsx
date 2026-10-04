"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ROLE_FA, faError } from "@/lib/labels";

interface U {
  id: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  totp_enabled: boolean;
}

export default function Admin() {
  const router = useRouter();
  const [users, setUsers] = useState<U[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setUsers(await api<U[]>("/admin/users"));
    } catch {
      router.replace("/");
    }
  }, [router]);
  useEffect(() => {
    load();
  }, [load]);

  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setError("");
    try {
      await api("/admin/users", { body: Object.fromEntries(f) });
      form.reset();
      load();
    } catch (err) {
      setError(faError(err));
    }
  }
  const patch = (id: string, body: object) =>
    api(`/admin/users/${id}`, { method: "PATCH", body }).then(load);

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">مدیریت کاربران</h1>
        <Link href="/" className="btn">
          بازگشت
        </Link>
      </div>

      <form onSubmit={create} className="card grid gap-2 p-3 sm:grid-cols-2">
        <input
          name="username"
          required
          minLength={3}
          placeholder="نام کاربری"
          className="input"
          dir="ltr"
        />
        <input name="display_name" required placeholder="نام نمایشی" className="input" />
        <input
          name="password"
          type="password"
          required
          minLength={10}
          placeholder="گذرواژه اولیه (حداقل ۱۰ نویسه)"
          className="input"
          dir="ltr"
          autoComplete="new-password"
        />
        <select name="role" className="input" defaultValue="content_lead" aria-label="نقش">
          {Object.entries(ROLE_FA).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button className="btn btn-primary sm:col-span-2">افزودن کاربر</button>
        {error && (
          <p role="alert" className="text-sm text-danger sm:col-span-2">
            {error}
          </p>
        )}
      </form>

      <ul className="space-y-2">
        {users.map((u) => (
          <li key={u.id} className="card flex flex-wrap items-center gap-2 p-3 text-sm">
            <span className="font-medium">{u.display_name}</span>
            <span className="text-muted" dir="ltr">
              {u.username}
            </span>
            <select
              aria-label="نقش"
              className="input !w-auto !py-1"
              value={u.role}
              onChange={(e) => patch(u.id, { role: e.target.value })}
            >
              {Object.entries(ROLE_FA).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <span className="badge border-line text-muted">
              {u.totp_enabled ? "۲FA فعال" : "۲FA در انتظار"}
            </span>
            <span className="ms-auto flex gap-2">
              <button className="btn" onClick={() => patch(u.id, { reset_2fa: true })}>
                بازنشانی ۲FA
              </button>
              <button className="btn" onClick={() => patch(u.id, { is_active: !u.is_active })}>
                {u.is_active ? "غیرفعال" : "فعال‌سازی"}
              </button>
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}

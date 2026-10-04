"use client";

import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { faError } from "@/lib/labels";

type Step =
  | { kind: "credentials" }
  | { kind: "totp"; token: string }
  | { kind: "enroll"; token: string; secret: string; uri: string };

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>({ kind: "credentials" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(faError(e instanceof ApiError ? e : { detail: "" }));
    } finally {
      setBusy(false);
    }
  }

  function onCredentials(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    run(async () => {
      const r = await api<{ status: string; challenge_token: string }>("/auth/login", {
        body: { username: f.get("username"), password: f.get("password") },
      });
      if (r.status === "totp_required") setStep({ kind: "totp", token: r.challenge_token });
      else {
        const s = await api<{ secret: string; otpauth_uri: string }>("/auth/enroll/start", {
          body: { challenge_token: r.challenge_token },
        });
        setStep({ kind: "enroll", token: r.challenge_token, secret: s.secret, uri: s.otpauth_uri });
      }
    });
  }

  function onCode(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (step.kind === "credentials") return;
    const code = String(new FormData(e.currentTarget).get("code")).trim();
    run(async () => {
      await api(step.kind === "enroll" ? "/auth/enroll/confirm" : "/auth/totp", {
        body: { challenge_token: step.token, code },
      });
      router.replace("/");
    });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm items-center px-4">
      <div className="card w-full space-y-4 p-6">
        <h1 className="text-xl font-bold">اتاق فرمان روایت</h1>

        {step.kind === "credentials" && (
          <form onSubmit={onCredentials} className="space-y-3">
            <label className="block text-sm">
              نام کاربری
              <input
                name="username"
                required
                autoComplete="username"
                className="input mt-1"
                dir="ltr"
              />
            </label>
            <label className="block text-sm">
              گذرواژه
              <input
                name="password"
                type="password"
                required
                autoComplete="current-password"
                className="input mt-1"
                dir="ltr"
              />
            </label>
            <button className="btn btn-primary w-full" disabled={busy}>
              ادامه
            </button>
          </form>
        )}

        {step.kind !== "credentials" && (
          <form onSubmit={onCode} className="space-y-3">
            {step.kind === "enroll" && (
              <div className="space-y-2 text-sm">
                <p>
                  برای فعال‌سازی ورود دومرحله‌ای، این QR را در برنامه احراز هویت (مانند Google
                  Authenticator) اسکن کنید.
                </p>
                <div className="flex justify-center rounded-md bg-white p-3">
                  <QRCodeSVG value={step.uri} size={160} />
                </div>
                <p className="text-muted">یا کلید را دستی وارد کنید:</p>
                <code
                  dir="ltr"
                  className="block select-all break-all rounded bg-raised p-2 text-center"
                >
                  {step.secret}
                </code>
              </div>
            )}
            <label className="block text-sm">
              کد ۶‌رقمی برنامه احراز هویت
              <input
                name="code"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                autoFocus
                autoComplete="one-time-code"
                className="input mt-1 text-center tracking-widest"
                dir="ltr"
              />
            </label>
            <button className="btn btn-primary w-full" disabled={busy}>
              {step.kind === "enroll" ? "فعال‌سازی و ورود" : "ورود"}
            </button>
          </form>
        )}

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}

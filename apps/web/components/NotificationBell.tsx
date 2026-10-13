"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { NotificationItem } from "@/lib/types";

const fa = (n: number) => n.toLocaleString("fa-IR");

export function NotificationBell() {
  const router = useRouter();
  const [box, setBox] = useState<{ unread: number; items: NotificationItem[] } | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(
    () =>
      api<{ unread: number; items: NotificationItem[] }>("/notifications")
        .then(setBox)
        .catch(() => {}),
    [],
  );
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  async function openItem(n: NotificationItem) {
    setOpen(false);
    if (!n.read) await api(`/notifications/${n.id}/read`, { body: {} }).catch(() => {});
    load();
    if (n.link) router.push(n.link);
  }

  return (
    <div className="relative">
      <button
        className="btn"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        aria-label={`اعلان‌ها${box?.unread ? `، ${fa(box.unread)} خوانده‌نشده` : ""}`}
      >
        اعلان‌ها
        {!!box?.unread && (
          <span className="badge ms-1.5 border-accent text-accent tabular-nums">
            {fa(box.unread)}
          </span>
        )}
      </button>
      {open && (
        <div
          role="menu"
          className="card absolute end-0 z-30 mt-1 w-80 max-w-[85vw] space-y-1 p-2 shadow-lg"
        >
          {box?.items.length === 0 && <p className="p-2 text-sm text-muted">اعلانی نیست.</p>}
          {box?.items.map((n) => (
            <button
              key={n.id}
              role="menuitem"
              onClick={() => openItem(n)}
              className="block w-full rounded-md p-2 text-start text-sm hover:bg-raised"
            >
              <div className={n.read ? "text-muted" : "font-medium"}>{n.title}</div>
              {n.body && <div className="text-xs text-muted">{n.body}</div>}
            </button>
          ))}
          {!!box?.unread && (
            <button
              className="btn w-full"
              onClick={() => api("/notifications/read-all", { body: {} }).then(load)}
            >
              علامت‌گذاری همه به‌عنوان خوانده‌شده
            </button>
          )}
        </div>
      )}
    </div>
  );
}

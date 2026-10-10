export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
  }
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; form?: FormData } = {},
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init.method ?? (init.body !== undefined || init.form ? "POST" : "GET"),
    // For multipart uploads the browser must set the content-type (with its boundary) itself.
    headers: init.form ? { "x-ncr": "1" } : { "content-type": "application/json", "x-ncr": "1" },
    body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined),
    credentials: "same-origin",
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

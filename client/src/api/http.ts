const isLocalhost =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

export const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (isLocalhost ? "http://localhost:8000" : window.location.origin);

export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string | null) {
  if (!token) localStorage.removeItem("token");
  else localStorage.setItem("token", token);
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const data: any = await res.clone().json();

    if (res.status === 422 && Array.isArray(data?.detail)) {
      return data.detail
        .map((d: any) => {
          const loc = Array.isArray(d.loc) ? d.loc : [];
          const field = loc.length ? String(loc[loc.length - 1]) : "field";
          return `${field}: ${d.msg ?? "Invalid value"}`;
        })
        .join("\n");
    }

    if (typeof data?.detail === "string") return data.detail;

    // If we ever send structured detail: { detail: { message: "..." } }
    if (typeof data?.detail?.message === "string") return data.detail.message;

    if (typeof data?.message === "string") return data.message;
  } catch {
    // not JSON
  }

  // Fallback to plain text
  try {
    const text = await res.text();
    if (text) return text;
  } catch {}

  return res.statusText || `Request failed (${res.status})`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const msg = await extractErrorMessage(res);
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  
  return (await res.json()) as T;
}

export function wsBaseUrl(): string {
  return API_BASE.replace(/^http/, "ws");
}

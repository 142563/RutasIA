/** Cliente de la API de Django: sesión por cookie + token CSRF en X-CSRFToken. */

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

async function ensureCsrfCookie(): Promise<string> {
  let token = getCookie("csrftoken");
  if (!token) {
    await fetch("/api/auth/csrf/", { credentials: "same-origin" });
    token = getCookie("csrftoken");
  }
  return token ?? "";
}

let onUnauthorized: (() => void) | null = null;
/** La app registra aquí qué hacer si la sesión expiró (ir al login). */
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export async function api<T>(path: string, options: { method?: string; body?: unknown; query?: Query } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = await ensureCsrfCookie();
  }
  let url = path;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(options.query)) if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      credentials: "same-origin",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError("No hay conexión con el servidor.", 0);
  }

  const data = await response.json().catch(() => null);
  if (!response.ok || !data || data.ok === false) {
    if (response.status === 401 && onUnauthorized) onUnauthorized();
    const message = data?.error ?? (response.status >= 500 ? "Error del servidor. Intenta de nuevo." : `Error ${response.status}`);
    throw new ApiError(message, response.status);
  }
  return data as T;
}

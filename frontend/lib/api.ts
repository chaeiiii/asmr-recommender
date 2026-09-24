export class ApiError extends Error {
  constructor(public status: number, public code?: string) { super("Request failed. Please try again."); }
}
export async function api<T>(path: string, body?: unknown, method?: "GET" | "POST" | "DELETE"): Promise<T> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/api/v1${path}`, {
    method: method ?? (body === undefined ? "GET" : "POST"), credentials: "include", cache: "no-store",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(response.status, error.detail?.code);
  }
  return response.json() as Promise<T>;
}
export type NextRoute = { next_route: string };
export type Session = NextRoute & { onboarding_completed: boolean };
let pending: Promise<Session> | undefined;
export function resumeSession() {
  if (!pending) pending = api<Session>("/session", {}).finally(() => { pending = undefined; });
  return pending;
}

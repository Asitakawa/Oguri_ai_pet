import type { StatusPayload } from "./types";

const TOKEN_KEY = "mgmt_token";

/** 从 URL 读取一次性 token 并存入 sessionStorage，随后从地址栏抹掉 */
export function initToken(): string {
  const params = new URLSearchParams(location.search);
  const t = params.get("token") ?? sessionStorage.getItem(TOKEN_KEY) ?? "";
  if (t) sessionStorage.setItem(TOKEN_KEY, t);
  if (params.has("token")) {
    params.delete("token");
    const qs = params.toString();
    history.replaceState(null, "", location.pathname + (qs ? `?${qs}` : "") + location.hash);
  }
  return t;
}

function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Management-Token": token } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let msg = `API ${path} -> ${res.status}`;
    try {
      const data = (await res.json()) as { error?: string };
      if (data.error) msg = data.error;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export const api = {
  getStatus(): Promise<StatusPayload> {
    return request<StatusPayload>("/api/status");
  },
  feed(): Promise<StatusPayload> {
    return request<StatusPayload>("/api/pet/feed", { method: "POST" });
  },
};

/** SSE 状态流；返回关闭函数 */
export function openStatusStream(
  onStatus: (s: StatusPayload) => void,
  onError?: () => void,
): () => void {
  const token = getToken();
  const es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
  es.addEventListener("status", (ev: MessageEvent) => {
    try {
      onStatus(JSON.parse(String(ev.data)) as StatusPayload);
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => onError?.();
  return () => es.close();
}
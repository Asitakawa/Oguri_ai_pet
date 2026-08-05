import type { ChatMessage, SettingsPayload } from "./types";

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Management-Token": token } : {}),
      ...(init.headers ?? {}),
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

async function requestText(path: string, init: RequestInit = {}): Promise<string> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(token ? { "X-Management-Token": token } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.text();
}

export const api = {
  getStatus() {
    return request<import("./types").StatusPayload>("/api/status");
  },
  feed() {
    return request<import("./types").StatusPayload>("/api/pet/feed", { method: "POST" });
  },
  getHistory(q = ""): Promise<{ messages: ChatMessage[] }> {
    return request(`/api/history${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  },
  sendChat(text: string): Promise<{ reply: string }> {
    return request("/api/chat", { method: "POST", body: JSON.stringify({ text }) });
  },
  clearHistory(): Promise<{ ok: boolean }> {
    return request("/api/history", { method: "DELETE" });
  },
  exportHistory(): Promise<string> {
    return requestText("/api/history/export");
  },
  getSettings(): Promise<SettingsPayload> {
    return request("/api/settings");
  },
  saveApi(p: { provider: string; model: string; apiKey: string }): Promise<{ ok: boolean }> {
    return request("/api/settings/api", { method: "POST", body: JSON.stringify(p) });
  },
  testApi(p: { provider: string; model: string; apiKey: string }): Promise<{ ok: boolean; message: string }> {
    return request("/api/settings/api/test", { method: "POST", body: JSON.stringify(p) });
  },
  saveSystem(s: SettingsPayload["system"]): Promise<{ ok: boolean }> {
    return request("/api/settings/system", { method: "POST", body: JSON.stringify(s) });
  },
  setPetSize(scale: number): Promise<{ ok: boolean }> {
    return request("/api/pet/size", { method: "POST", body: JSON.stringify({ scale }) });
  },
  saveFont(family: string, size: number): Promise<{ ok: boolean }> {
    return request("/api/settings/font", { method: "POST", body: JSON.stringify({ family, size }) });
  },
  restartPet(): Promise<{ ok: boolean }> {
    return request("/api/pet/restart", { method: "POST", body: "{}" });
  },
  quitPet(): Promise<{ ok: boolean }> {
    return request("/api/pet/quit", { method: "POST", body: "{}" });
  },
};

/** SSE 状态流；返回关闭函数 */
export function openStatusStream(
  onStatus: (s: import("./types").StatusPayload) => void,
  onError?: () => void,
): () => void {
  const token = getToken();
  const es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
  es.addEventListener("status", (ev: MessageEvent) => {
    try {
      onStatus(JSON.parse(String(ev.data)) as import("./types").StatusPayload);
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => onError?.();
  return () => es.close();
}
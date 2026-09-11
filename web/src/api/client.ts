import type { ChatMessage, GameInfo, LogPayload, MemoryPayload, SkillDetail, SkillInfo, SettingsPayload } from "./types";

const TOKEN_KEY = "mgmt_token";

/** 带 HTTP 状态码的错误：让视图能区分「桌宠没开」和「token 失效」 */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** 把任意异常转成给用户看的提示。401/403 单独说明，否则会误导成「桌宠没启动」。 */
export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401 || e.status === 403) {
      return "访问令牌已失效：桌宠每次启动都会更换地址与 token，请从桌宠右键菜单重新打开管理面板";
    }
    return `请求失败（HTTP ${e.status}）`;
  }
  return "无法连接到桌宠服务：请确认桌宠正在运行";
}

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
    throw new ApiError(res.status, msg);
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
  if (!res.ok) throw new ApiError(res.status, `API ${path} -> ${res.status}`);
  return res.text();
}

export const api = {
  getStatus() {
    return request<import("./types").StatusPayload>("/api/status");
  },
  getLogs(lines = 200): Promise<LogPayload> {
    return request(`/api/logs?lines=${lines}`);
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
  saveSystem(s: Partial<SettingsPayload["system"]>): Promise<{ ok: boolean }> {
    return request("/api/settings/system", { method: "POST", body: JSON.stringify(s) });
  },
  setPetSize(scale: number): Promise<{ ok: boolean; scale: number }> {
    return request("/api/pet/size", { method: "POST", body: JSON.stringify({ scale }) });
  },
  saveFont(family: string, size: number): Promise<{ ok: boolean; family: string; size: number }> {
    return request("/api/settings/font", { method: "POST", body: JSON.stringify({ family, size }) });
  },
  restartPet(): Promise<{ ok: boolean }> {
    return request("/api/pet/restart", { method: "POST", body: "{}" });
  },
  getGames(): Promise<{ games: GameInfo[]; active: string | null }> {
    return request("/api/games");
  },
  toggleGame(key: string, enabled: boolean): Promise<{ games: GameInfo[]; active: string | null }> {
    return request(`/api/games/${encodeURIComponent(key)}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) });
  },
  startGame(key: string): Promise<{ games: GameInfo[]; active: string | null }> {
    return request(`/api/games/${encodeURIComponent(key)}/start`, { method: "POST", body: "{}" });
  },
  stopGame(): Promise<{ games: GameInfo[]; active: string | null }> {
    return request("/api/games/stop", { method: "POST", body: "{}" });
  },
  getSkills(): Promise<{ skills: SkillInfo[] }> {
    return request("/api/skills");
  },
  getSkillDetail(name: string): Promise<SkillDetail> {
    return request(`/api/skills/${encodeURIComponent(name)}`);
  },
  toggleSkill(name: string, enabled: boolean): Promise<{ ok: boolean }> {
    return request(`/api/skills/${encodeURIComponent(name)}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) });
  },
  executeSkill(name: string, args: Record<string, unknown>): Promise<{ result: string }> {
    return request(`/api/skills/${encodeURIComponent(name)}/execute`, { method: "POST", body: JSON.stringify({ arguments: args }) });
  },
  deleteSkill(name: string): Promise<{ ok: boolean }> {
    return request(`/api/skills/${encodeURIComponent(name)}`, { method: "DELETE" });
  },
  importSkill(filename: string, contentBase64: string): Promise<{ ok: boolean; message: string }> {
    return request("/api/skills/import", { method: "POST", body: JSON.stringify({ filename, content: contentBase64 }) });
  },
  quitPet(): Promise<{ ok: boolean }> {
    return request("/api/pet/quit", { method: "POST", body: "{}" });
  },
  // ---- 长期记忆 ----
  getMemory(): Promise<MemoryPayload> {
    return request("/api/memory");
  },
  setMemoryEnabled(enabled: boolean): Promise<{ ok: boolean; memory: MemoryPayload }> {
    return request("/api/memory", { method: "POST", body: JSON.stringify({ enabled }) });
  },
  addMemory(text: string): Promise<{ ok: boolean; added: boolean; memory: MemoryPayload }> {
    return request("/api/memory", { method: "POST", body: JSON.stringify({ text }) });
  },
  deleteMemory(id: string): Promise<{ ok: boolean }> {
    return request(`/api/memory/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  clearMemory(): Promise<{ ok: boolean; cleared: number }> {
    return request("/api/memory", { method: "DELETE" });
  },
  setAutostart(enabled: boolean): Promise<{ ok: boolean; message: string; enabled: boolean }> {
    return request("/api/settings/autostart", { method: "POST", body: JSON.stringify({ enabled }) });
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

/** 实时终端日志流；返回关闭函数。offset 为起始字节位置（配合 /api/logs 初次拉取防丢行） */
export function openLogStream(
  onLog: (lines: string[]) => void,
  onError?: () => void,
  offset = 0,
): () => void {
  const token = getToken();
  const es = new EventSource(`/api/logs/stream?token=${encodeURIComponent(token)}&offset=${offset}`);
  es.addEventListener("log", (ev: MessageEvent) => {
    try {
      const data = JSON.parse(String(ev.data)) as { lines: string[] };
      onLog(data.lines);
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => onError?.();
  return () => es.close();
}
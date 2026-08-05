import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api } from "../api/client";
import type { ChatMessage } from "../api/types";
import { escapeHtml } from "../utils";

function fmtTime(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function msgHTML(m: ChatMessage): string {
  const isUser = m.role === "user";
  return `
  <div class="chat-msg ${isUser ? "user" : "pet"}">
    <div class="chat-avatar">${isUser ? "🧑‍💻" : "🍥"}</div>
    <div class="chat-bubble">
      <div class="chat-meta">${isUser ? "训练员" : "小栗帽"} · ${escapeHtml(m.timestamp)}</div>
      <div class="chat-text">${escapeHtml(m.content)}</div>
    </div>
  </div>`;
}

function scrollBottom(): void {
  const list = document.getElementById("chat-list");
  if (list) list.scrollTop = list.scrollHeight;
}

export const Chat: View = {
  id: "chat",
  title: "聊天",
  icon: "💬",
  render() {
    return `
    <div class="view view-chat">
      <section class="glass-card chat-panel">
        <div class="chat-toolbar">
          <input id="chat-search" class="input" type="search" placeholder="搜索聊天记录…" />
          <button class="btn" data-action="export">⬇ 导出</button>
          <button class="btn btn-danger" data-action="clear">🗑 清空</button>
        </div>
        <div class="chat-list" id="chat-list"><div class="chat-empty">加载中…</div></div>
        <div class="chat-input-row">
          <input id="chat-input" class="input" placeholder="和小栗帽说点什么…" autocomplete="off" />
          <button class="btn btn-primary" data-action="send">发送</button>
        </div>
      </section>
    </div>`;
  },
  async mount(ctx: Ctx) {
    gsap.from(".chat-panel", { opacity: 0, y: 14, duration: 0.35, ease: "power2.out" });
    const listEl = () => document.getElementById("chat-list");
    const inputEl = () => document.getElementById("chat-input") as HTMLInputElement | null;
    const searchEl = () => document.getElementById("chat-search") as HTMLInputElement | null;

    const load = async (q = "") => {
      try {
        const { messages } = await api.getHistory(q);
        const el = listEl();
        if (el) {
          el.innerHTML = messages.length
            ? messages.map(msgHTML).join("")
            : '<div class="chat-empty">还没有聊天记录，去和小栗帽说句话吧</div>';
        }
        scrollBottom();
      } catch {
        const el = listEl();
        if (el) el.innerHTML = '<div class="chat-empty">无法加载聊天记录（未连接桌宠）</div>';
      }
    };

    const thinking = (on: boolean) => {
      const el = listEl();
      if (!el) return;
      const existing = el.querySelector(".chat-thinking");
      if (on && !existing) {
        el.insertAdjacentHTML("beforeend", '<div class="chat-thinking">小栗帽正在思考…</div>');
      } else if (!on && existing) {
        existing.remove();
      }
      scrollBottom();
    };

    const send = async () => {
      const inp = inputEl();
      const text = inp?.value.trim() ?? "";
      if (!text) return;
      if (inp) inp.value = "";
      thinking(true);
      try {
        await api.sendChat(text);
        await load(searchEl()?.value.trim() ?? "");
      } catch {
        listEl()?.insertAdjacentHTML(
          "beforeend",
          '<div class="chat-empty">发送失败（未连接桌宠或 AI 未配置）</div>',
        );
      } finally {
        thinking(false);
      }
    };

    ctx.root.querySelector("[data-action='send']")?.addEventListener("click", () => void send());
    inputEl()?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") void send();
    });
    searchEl()?.addEventListener("input", () => void load(searchEl()?.value.trim() ?? ""));
    ctx.root.querySelector("[data-action='clear']")?.addEventListener("click", async () => {
      if (!window.confirm("确定要清空所有聊天记录吗？此操作不可恢复。")) return;
      try {
        await api.clearHistory();
        await load();
      } catch {
        /* ignore */
      }
    });
    ctx.root.querySelector("[data-action='export']")?.addEventListener("click", async () => {
      try {
        const text = await api.exportHistory();
        const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `chat_history_${fmtTime()}.txt`;
        a.click();
        URL.revokeObjectURL(a.href);
      } catch {
        /* ignore */
      }
    });

    void load();
  },
};
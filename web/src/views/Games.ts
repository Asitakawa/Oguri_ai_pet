import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api, describeError } from "../api/client";
import type { GameInfo } from "../api/types";
import { escapeHtml } from "../utils";

/** 桌宠侧可能自行结束游戏，轮询间隔取 SSE 状态推送的两倍左右 */
const POLL_MS = 5000;

function cardHTML(g: GameInfo): string {
  return `
  <div class="game-card ${g.active ? "active" : ""}">
    <div class="game-head">
      <b>${escapeHtml(g.name)}</b>
      ${g.active
        ? '<span class="badge badge-active">游玩中</span>'
        : g.enabled
          ? '<span class="badge">已启用</span>'
          : '<span class="badge badge-off">已停用</span>'}
    </div>
    <p class="game-desc">${escapeHtml(g.desc || "（无描述）")}</p>
    <div class="game-actions">
      <label class="switch" title="启用/停用">
        <input type="checkbox" data-key="${escapeHtml(g.key)}" ${g.enabled ? "checked" : ""} ${g.active ? "disabled" : ""}/>
        <span></span>
      </label>
      ${g.active
        ? '<button class="btn btn-danger btn-sm" data-action="stop">退出游戏</button>'
        : `<button class="btn btn-primary btn-sm" data-action="start" data-key="${escapeHtml(g.key)}" ${g.enabled ? "" : "disabled"}>启动</button>`}
    </div>
  </div>`;
}

/** 用于判断轮询结果是否真的变化，避免无谓重绘打断交互 */
function fingerprint(games: GameInfo[], active: string | null): string {
  return JSON.stringify([active, games.map((g) => [g.key, g.enabled, g.active])]);
}

// 模块级清理句柄。router 每次渲染前都会先 unmount，所以这里可以安全覆盖
let pollTimer: number | undefined;
let visibilityHandler: (() => void) | null = null;

function stopPolling(): void {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
  if (visibilityHandler) {
    document.removeEventListener("visibilitychange", visibilityHandler);
    visibilityHandler = null;
  }
}

export const Games: View = {
  id: "games",
  title: "游戏",
  render() {
    return `
    <div class="view view-games">
      <section class="glass-card">
        <header class="card-head"><h3>小游戏</h3></header>
        <div class="game-grid" id="game-grid"><div class="chat-empty">加载中…</div></div>
      </section>
    </div>`;
  },
  async mount(_ctx: Ctx) {
    gsap.from(".view-games .glass-card", { opacity: 0, y: 16, duration: 0.35, ease: "power2.out" });
    const grid = document.getElementById("game-grid");

    let lastPrint = "";

    const render = (games: GameInfo[], active: string | null) => {
      lastPrint = fingerprint(games, active);
      if (grid) {
        grid.innerHTML = games.length
          ? games.map(cardHTML).join("")
          : '<div class="chat-empty">没有可用游戏</div>';
      }
    };

    const load = async () => {
      try {
        const { games, active } = await api.getGames();
        // 状态没变就不要重绘：否则每 5 秒重建一次 DOM，
        // 正在操作开关的用户会看到点击被吞掉
        if (fingerprint(games, active) === lastPrint) return;
        render(games, active);
      } catch (e) {
        if (!lastPrint && grid) {
          grid.innerHTML = `<div class="chat-empty">${escapeHtml(describeError(e))}</div>`;
        }
      }
    };

    const startPolling = () => {
      if (pollTimer !== undefined) return;
      pollTimer = window.setInterval(() => void load(), POLL_MS);
    };
    const stopMyPolling = () => {
      if (pollTimer !== undefined) {
        window.clearInterval(pollTimer);
        pollTimer = undefined;
      }
    };

    // 隐藏时停轮询，避免后台标签页持续打请求
    visibilityHandler = () => {
      if (document.hidden) {
        stopMyPolling();
      } else {
        void load();
        startPolling();
      }
    };
    document.addEventListener("visibilitychange", visibilityHandler);

    grid?.addEventListener("click", async (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (!btn) return;
      try {
        if (btn.dataset.action === "start") {
          const { games, active } = await api.startGame(btn.dataset.key ?? "");
          render(games, active);
        } else if (btn.dataset.action === "stop") {
          const { games, active } = await api.stopGame();
          render(games, active);
        }
      } catch {
        lastPrint = ""; // 失败时强制回读真实状态，避免界面停在乐观值上
        await load();
      }
    });

    grid?.addEventListener("change", async (e) => {
      const t = e.target as HTMLInputElement;
      if (t.type !== "checkbox" || !t.dataset.key) return;
      try {
        const { games, active } = await api.toggleGame(t.dataset.key, t.checked);
        render(games, active);
      } catch {
        t.checked = !t.checked;
      }
    });

    await load();
    startPolling();
  },
  unmount() {
    stopPolling();
  },
};

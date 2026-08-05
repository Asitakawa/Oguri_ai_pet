import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api } from "../api/client";
import type { GameInfo } from "../api/types";
import { escapeHtml } from "../utils";

function cardHTML(g: GameInfo): string {
  return `
  <div class="game-card ${g.active ? "active" : ""}">
    <div class="game-head">
      <b>${escapeHtml(g.name)}</b>
      ${g.active
        ? '<span class="badge badge-active">▶ 游玩中</span>'
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
        ? '<button class="btn btn-danger btn-sm" data-action="stop">⏹ 退出游戏</button>'
        : `<button class="btn btn-primary btn-sm" data-action="start" data-key="${escapeHtml(g.key)}" ${g.enabled ? "" : "disabled"}>▶ 启动</button>`}
    </div>
  </div>`;
}

export const Games: View = {
  id: "games",
  title: "游戏",
  icon: "🎮",
  render() {
    return `
    <div class="view view-games">
      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🎮</span><h3>小游戏</h3></header>
        <div class="game-grid" id="game-grid"><div class="chat-empty">加载中…</div></div>
      </section>
    </div>`;
  },
  async mount(_ctx: Ctx) {
    gsap.from(".view-games .glass-card", { opacity: 0, y: 16, duration: 0.35, ease: "power2.out" });
    const grid = document.getElementById("game-grid");

    const render = (games: GameInfo[]) => {
      if (grid) {
        grid.innerHTML = games.length
          ? games.map(cardHTML).join("")
          : '<div class="chat-empty">没有可用游戏</div>';
      }
    };

    const load = async () => {
      try {
        const { games } = await api.getGames();
        render(games);
      } catch {
        if (grid) grid.innerHTML = '<div class="chat-empty">无法加载游戏（未连接桌宠）</div>';
      }
    };

    grid?.addEventListener("click", async (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (!btn) return;
      try {
        if (btn.dataset.action === "start") {
          const { games } = await api.startGame(btn.dataset.key ?? "");
          render(games);
        } else if (btn.dataset.action === "stop") {
          const { games } = await api.stopGame();
          render(games);
        }
      } catch {
        /* ignore */
      }
    });

    grid?.addEventListener("change", async (e) => {
      const t = e.target as HTMLInputElement;
      if (t.type !== "checkbox" || !t.dataset.key) return;
      try {
        const { games } = await api.toggleGame(t.dataset.key, t.checked);
        render(games);
      } catch {
        t.checked = !t.checked;
      }
    });

    void load();
  },
};
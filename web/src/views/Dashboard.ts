import { gsap } from "gsap";
import type { View } from "./types";
import { api } from "../api/client";
import { petAvatarHTML } from "../components/PetAvatar";
import { ringHTML, ringUpdate } from "../components/StatusRing";
import { cardHTML } from "../components/GlassCard";

function fmtUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h} 小时 ${m} 分`;
}

let unsub: (() => void) | null = null;

export const Dashboard: View = {
  id: "dashboard",
  title: "仪表盘",
  icon: "🏠",
  render(ctx) {
    const s = ctx.store.getState();
    const cpu = s.sysCpu == null ? "—" : `${Math.round(s.sysCpu)}%`;
    const mem = s.sysMemMB == null ? "—" : `${Math.round(s.sysMemMB)}MB`;
    return `
    <div class="view view-dashboard">
      <section class="dash-hero glass-card">
        <div class="dash-hero-left">${petAvatarHTML()}</div>
        <div class="dash-hero-mid">
          <h2>你好，训练员</h2>
          <p class="dash-sub">${s.connected ? "小栗帽在线，状态实时同步中" : "未连接桌宠（可能已退出或重启）"}</p>
          <div class="quick-actions">
            <button class="btn btn-primary" data-action="feed">🍙 喂饭团</button>
            <button class="btn" data-action="chat">💬 打开聊天</button>
            <button class="btn" data-action="game">🎮 快速开一局</button>
          </div>
        </div>
        <div class="dash-hero-right">
          ${ringHTML({ id: "ring-hunger", label: "饱腹", icon: "🍙", pct: s.hunger, color: "--c-rose" })}
          ${ringHTML({ id: "ring-energy", label: "活力", icon: "⚡", pct: s.energy, color: "--c-sky" })}
        </div>
      </section>
      <section class="dash-stats">
        ${cardHTML("陪伴统计", `
          <div class="stat-grid">
            <div class="stat"><b>${s.chatRounds}</b><span>累计聊天轮</span></div>
            <div class="stat"><b>${fmtUptime(s.uptimeSec)}</b><span>本次运行</span></div>
            <div class="stat"><b>${s.enabledSkills}/${s.totalSkills}</b><span>已启用技能</span></div>
            <div class="stat"><b>${cpu}</b><span>CPU</span></div>
          </div>`, { icon: "📊" })}
        ${cardHTML("进程", `
          <div class="stat-grid">
            <div class="stat"><b>${mem}</b><span>内存占用</span></div>
            <div class="stat"><b>${s.connected ? "在线" : "离线"}</b><span>桌宠连接</span></div>
          </div>`, { icon: "🖥️" })}
      </section>
    </div>`;
  },
  mount(ctx) {
    gsap.from(".dash-hero", { opacity: 0, y: 24, duration: 0.5, ease: "power2.out" });
    gsap.from(".dash-stats .glass-card", { opacity: 0, y: 16, duration: 0.4, delay: 0.15, ease: "power2.out" });

    unsub = ctx.store.subscribe(() => {
      const s = ctx.store.getState();
      ringUpdate("ring-hunger", s.hunger);
      ringUpdate("ring-energy", s.energy);
      document.getElementById("ring-hunger-wrap")?.classList.toggle("low", s.hunger < 30);
      document.getElementById("ring-energy-wrap")?.classList.toggle("low", s.energy < 25);
    });

    ctx.root.querySelector("[data-action='feed']")?.addEventListener("click", async () => {
      try {
        const st = await api.feed();
        ctx.store.setState({ ...st, connected: true });
      } catch {
        ctx.store.setState({ connected: false });
      }
    });
    ctx.root.querySelector("[data-action='chat']")?.addEventListener("click", () => ctx.navigate("chat"));
    ctx.root.querySelector("[data-action='game']")?.addEventListener("click", () => ctx.navigate("games"));
  },
  unmount() {
    unsub?.();
    unsub = null;
  },
};
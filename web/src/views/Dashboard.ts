import { gsap } from "gsap";
import type { View } from "./types";
import { api, openLogStream } from "../api/client";
import { petAvatarHTML } from "../components/PetAvatar";
import { ringHTML, ringUpdate } from "../components/StatusRing";
import { cardHTML } from "../components/GlassCard";

function fmtUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h} 小时 ${m} 分`;
}

let unsub: (() => void) | null = null;
let closeLog: (() => void) | null = null;
let terminalCollapsed = false;

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
            <div class="stat"><b data-count="${s.chatRounds}">${s.chatRounds}</b><span>累计聊天轮</span></div>
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
      <section class="glass-card dash-terminal" id="dash-terminal">
        <header class="term-head">
          <div class="term-title">
            <span class="term-dot" id="term-dot"></span>
            <span>实时终端</span>
            <span class="term-conn" id="term-conn">连接中…</span>
          </div>
          <div class="term-tools">
            <button class="btn btn-sm" id="term-pause" data-term="pause">⏸ 暂停</button>
            <button class="btn btn-sm" id="term-clear" data-term="clear">🧹 清空</button>
            <button class="btn btn-sm" id="term-toggle" data-term="toggle">▾ 折叠</button>
          </div>
        </header>
        <div class="term-body" id="term-body">
          <div class="term-output" id="term-output"></div>
        </div>
      </section>
    </div>`;
  },
  mount(ctx) {
    gsap.from(".dash-hero", { opacity: 0, y: 32, scale: 0.97, duration: 0.6, ease: "back.out(1.4)" });
    gsap.from(".dash-hero-left", { opacity: 0, scale: 0.8, duration: 0.6, delay: 0.12, ease: "back.out(1.6)" });
    gsap.from(".dash-stats .glass-card", { opacity: 0, y: 22, duration: 0.5, delay: 0.25, stagger: 0.12, ease: "back.out(1.2)" });

    // ---- 实时终端 ----
    gsap.from(".dash-terminal", { opacity: 0, y: 16, duration: 0.4, delay: 0.2, ease: "power2.out" });
    const termEl = document.getElementById("dash-terminal");
    const termBody = document.getElementById("term-body");
    const termOut = document.getElementById("term-output");
    const termDot = document.getElementById("term-dot");
    const termConn = document.getElementById("term-conn");
    const termPause = document.getElementById("term-pause");
    const termToggle = document.getElementById("term-toggle");
    if (terminalCollapsed) termEl?.classList.add("collapsed");
    if (termToggle) termToggle.textContent = terminalCollapsed ? "▸ 展开" : "▾ 折叠";

    let offset = 0;
    let paused = false;
    let autoScroll = true;

    const levelClass = (line: string): string =>
      /\[ERROR\]/.test(line) ? " err"
        : /\[WARNING\]/.test(line) ? " warn"
          : /\[INFO\]/.test(line) ? " info"
            : /\[DEBUG\]/.test(line) ? " debug"
              : "";

    const appendLines = (lines: string[]) => {
      if (!termOut) return;
      for (const line of lines) {
        const div = document.createElement("div");
        div.className = `term-line${levelClass(line)}`;
        div.textContent = line;
        termOut.appendChild(div);
      }
      while (termOut.childElementCount > 1200) termOut.removeChild(termOut.firstElementChild!);
      if (autoScroll && termBody) termBody.scrollTop = termBody.scrollHeight;
    };

    const startStream = () => {
      closeLog = openLogStream(
        (lines) => {
          if (!paused) appendLines(lines);
        },
        () => {
          if (termConn) termConn.textContent = "已断开";
          if (termDot) termDot.classList.add("off");
        },
        offset,
      );
    };

    api.getLogs(200)
      .then(({ lines, offset: o }) => {
        offset = o;
        appendLines(lines);
        if (termConn) termConn.textContent = "实时";
        startStream();
      })
      .catch(() => {
        if (termConn) termConn.textContent = "未连接";
        if (termDot) termDot.classList.add("off");
        startStream();
      });

    termBody?.addEventListener("scroll", () => {
      if (!termBody) return;
      autoScroll = termBody.scrollHeight - termBody.scrollTop - termBody.clientHeight < 30;
    });
    termToggle?.addEventListener("click", () => {
      terminalCollapsed = !terminalCollapsed;
      termEl?.classList.toggle("collapsed", terminalCollapsed);
      if (termToggle) termToggle.textContent = terminalCollapsed ? "▸ 展开" : "▾ 折叠";
      if (!terminalCollapsed && termBody) termBody.scrollTop = termBody.scrollHeight;
    });
    termPause?.addEventListener("click", () => {
      paused = !paused;
      if (termPause) {
        termPause.textContent = paused ? "▶ 继续" : "⏸ 暂停";
        termPause.classList.toggle("active", paused);
      }
    });
    document.getElementById("term-clear")?.addEventListener("click", () => {
      if (termOut) termOut.innerHTML = "";
    });

    // ---- 数字滚动动画 ----
    const animateCount = (el: HTMLElement, to: number, dur = 0.8) => {
      const obj = { v: 0 };
      gsap.to(obj, {
        v: to,
        duration: dur,
        ease: "power2.out",
        onUpdate: () => {
          el.textContent = String(Math.round(obj.v));
        },
      });
    };
    document.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
      animateCount(el, Number(el.dataset.count ?? 0));
    });

    unsub = ctx.store.subscribe(() => {
      const s = ctx.store.getState();
      ringUpdate("ring-hunger", s.hunger);
      ringUpdate("ring-energy", s.energy);
      const cntEl = document.querySelector<HTMLElement>("[data-count]");
      if (cntEl && s.chatRounds !== Number(cntEl.dataset.count)) {
        cntEl.dataset.count = String(s.chatRounds);
        animateCount(cntEl, s.chatRounds, 0.6);
      }
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
    closeLog?.();
    closeLog = null;
    unsub?.();
    unsub = null;
  },
};
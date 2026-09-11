import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api, describeError, openLogStream } from "../api/client";
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

/** 终端滚动缓冲区上限（DOM 行数） */
const TERM_MAX_LINES = 1200;
/** 暂停期间最多缓存的待补行数，超出则丢最旧的并提示 */
const TERM_PAUSE_BUFFER = 4000;

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
          <p class="dash-sub" id="dash-sub">${s.connected ? "小栗帽在线，状态实时同步中" : "未连接桌宠（可能已退出或重启）"}</p>
          <div class="quick-actions">
            <button class="btn btn-primary" data-action="feed">🍙 喂饭团</button>
            <button class="btn" data-action="chat">💬 打开聊天</button>
            <button class="btn" data-action="game">🎮 快速开一局</button>
          </div>
        </div>
        <div class="dash-hero-right">
          ${ringHTML({ id: "ring-hunger", label: "饱腹", icon: "🍙", pct: s.hunger, color: "--ring-hunger" })}
          ${ringHTML({ id: "ring-energy", label: "活力", icon: "⚡", pct: s.energy, color: "--ring-energy" })}
        </div>
      </section>
      <section class="dash-stats">
        ${cardHTML("陪伴统计", `
          <div class="stat-grid">
            <div class="stat"><b data-count="${s.chatRounds}">${s.chatRounds}</b><span>累计聊天轮</span></div>
            <div class="stat"><b id="dash-uptime">${fmtUptime(s.uptimeSec)}</b><span>本次运行</span></div>
            <div class="stat"><b id="dash-skills">${s.enabledSkills}/${s.totalSkills}</b><span>已启用技能</span></div>
            <div class="stat"><b id="dash-cpu">${cpu}</b><span>CPU</span></div>
          </div>`, { icon: "📊" })}
        ${s.companion ? cardHTML("一起走过", `
          <div class="stat-grid">
            <div class="stat"><b id="dash-days">${s.companion.daysTogether}</b><span>相处天数</span></div>
            <div class="stat"><b id="dash-total">${s.companion.totalHours}h</b><span>累计陪伴</span></div>
            <div class="stat"><b id="dash-feed">${s.companion.feedCount}</b><span>喂食次数</span></div>
            <div class="stat"><b id="dash-games">${s.companion.gamesPlayed}</b><span>开局次数</span></div>
            <div class="stat"><b id="dash-fly">${s.companion.maxFlyMeters}m</b><span>飞行纪录</span></div>
            <div class="stat"><b id="dash-drag">${s.companion.dragCount}</b><span>被拖走</span></div>
          </div>`, { icon: "🍙" }) : ""}
        ${cardHTML("进程", `
          <div class="stat-grid">
            <div class="stat"><b id="dash-mem">${mem}</b><span>内存占用</span></div>
            <div class="stat"><b id="dash-online">${s.connected ? "在线" : "离线"}</b><span>桌宠连接</span></div>
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
  mount(ctx: Ctx) {
    gsap.from(".dash-hero", { opacity: 0, y: 32, scale: 0.97, duration: 0.6, ease: "back.out(1.4)" });
    gsap.from(".dash-hero-left", { opacity: 0, scale: 0.8, duration: 0.6, delay: 0.12, ease: "back.out(1.6)" });
    gsap.from(".dash-stats .glass-card", { opacity: 0, y: 22, duration: 0.5, delay: 0.25, stagger: 0.12, ease: "back.out(1.2)" });

    // 本视图被重复挂载时，先清掉上一轮遗留的订阅与流（模块级变量会被覆盖，
    // 不主动断开会永久泄漏）
    unsub?.();
    unsub = null;
    closeLog?.();
    closeLog = null;

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
    // 暂停期间把行攒起来，继续时补上。后端日志游标是服务端自己推进的，
    // 前端丢弃就等于永久丢日志。
    let pending: string[] = [];

    const levelClass = (line: string): string =>
      /\[ERROR\]/.test(line) ? " err"
        : /\[WARNING\]/.test(line) ? " warn"
          : /\[INFO\]/.test(line) ? " info"
            : /\[DEBUG\]/.test(line) ? " debug"
              : "";

    const appendLines = (lines: string[]) => {
      if (!termOut || !lines.length) return;
      const frag = document.createDocumentFragment();
      for (const line of lines) {
        const div = document.createElement("div");
        div.className = `term-line${levelClass(line)}`;
        div.textContent = line;
        frag.appendChild(div);
      }
      termOut.appendChild(frag);
      while (termOut.childElementCount > TERM_MAX_LINES) {
        termOut.removeChild(termOut.firstElementChild!);
      }
      if (autoScroll && termBody) termBody.scrollTop = termBody.scrollHeight;
    };

    const startStream = () => {
      closeLog = openLogStream(
        (lines) => {
          if (paused) {
            pending.push(...lines);
            if (pending.length > TERM_PAUSE_BUFFER) {
              const dropped = pending.length - TERM_PAUSE_BUFFER;
              pending = pending.slice(dropped);
              pending.unshift(`… 已丢弃 ${dropped} 行（暂停期间缓存溢出）`);
            }
            return;
          }
          appendLines(lines);
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
        // 首拉失败时不要用 offset=0 起流：后端会从文件头重放整个日志。
        // 改从当前末尾开始追加，宁可少一次历史，也不要整文件回灌。
        if (termConn) termConn.textContent = "未连接";
        if (termDot) termDot.classList.add("off");
        api.getLogs(1)
          .then(({ offset: o }) => {
            offset = o;
            startStream();
          })
          .catch((e: unknown) => {
            if (termConn) termConn.textContent = describeError(e);
            offset = Number.MAX_SAFE_INTEGER; // 触发后端「offset 大于文件」分支，只回最近内容
            startStream();
          });
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
      if (!paused && pending.length) {
        const flush = pending;
        pending = [];
        appendLines(flush);
      }
    });
    document.getElementById("term-clear")?.addEventListener("click", () => {
      pending = [];
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

    // ---- 状态同步 ----
    // 之前只在 render() 时读一次 store，导致 uptime/CPU/内存/技能数/在线状态
    // 在停留本页期间永远不刷新；这里把每个会变的量都接上
    const setText = (id: string, text: string) => {
      const el = document.getElementById(id);
      if (el && el.textContent !== text) el.textContent = text;
    };

    let prev = ctx.store.getState();

    unsub = ctx.store.subscribe(() => {
      const s = ctx.store.getState();

      ringUpdate("ring-hunger", s.hunger);
      ringUpdate("ring-energy", s.energy);
      document.getElementById("ring-hunger-wrap")?.classList.toggle("low", s.hunger < 30);
      document.getElementById("ring-energy-wrap")?.classList.toggle("low", s.energy < 25);

      if (s.chatRounds !== prev.chatRounds) {
        const cntEl = document.querySelector<HTMLElement>("[data-count]");
        if (cntEl) {
          cntEl.dataset.count = String(s.chatRounds);
          animateCount(cntEl, s.chatRounds, 0.6);
        }
      }
      if (s.uptimeSec !== prev.uptimeSec) setText("dash-uptime", fmtUptime(s.uptimeSec));
      if (s.sysCpu !== prev.sysCpu) setText("dash-cpu", s.sysCpu == null ? "—" : `${Math.round(s.sysCpu)}%`);
      if (s.sysMemMB !== prev.sysMemMB) setText("dash-mem", s.sysMemMB == null ? "—" : `${Math.round(s.sysMemMB)}MB`);
      if (s.enabledSkills !== prev.enabledSkills || s.totalSkills !== prev.totalSkills) {
        setText("dash-skills", `${s.enabledSkills}/${s.totalSkills}`);
      }
      if (s.connected !== prev.connected) {
        setText("dash-online", s.connected ? "在线" : "离线");
        setText("dash-sub", s.connected ? "小栗帽在线，状态实时同步中" : "未连接桌宠（可能已退出或重启）");
      }
      if (s.companion) {
        const c = s.companion;
        const pc = prev.companion;
        if (!pc || c.daysTogether !== pc.daysTogether) setText("dash-days", String(c.daysTogether));
        if (!pc || c.totalHours !== pc.totalHours) setText("dash-total", `${c.totalHours}h`);
        if (!pc || c.feedCount !== pc.feedCount) setText("dash-feed", String(c.feedCount));
        if (!pc || c.gamesPlayed !== pc.gamesPlayed) setText("dash-games", String(c.gamesPlayed));
        if (!pc || c.maxFlyMeters !== pc.maxFlyMeters) setText("dash-fly", `${c.maxFlyMeters}m`);
        if (!pc || c.dragCount !== pc.dragCount) setText("dash-drag", String(c.dragCount));
      }

      prev = s;
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

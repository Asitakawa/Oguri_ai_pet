import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import { createStore, initialState } from "./store";
import { createRouter } from "./router";
import { routes, type Ctx } from "./views";
import { api, initToken, openStatusStream } from "./api/client";
import type { StatusPayload } from "./api/types";

initToken();

const store = createStore(initialState);
const app = document.getElementById("app");
if (!app) throw new Error("#app not found");

app.innerHTML = `
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar-brand"><span class="brand-dot"></span><span>小栗帽管理面板</span></div>
      <nav class="nav" id="nav"></nav>
      <div class="sidebar-foot">v0.2 · 阶段 2</div>
    </aside>
    <div class="main">
      <header class="topbar">
        <h1 id="topbar-title">仪表盘</h1>
        <div class="topbar-status">
          <div class="mini-bar"><span>饱腹</span><div class="mini-track"><div class="mini-fill rose" id="mini-hunger"></div></div></div>
          <div class="mini-bar"><span>活力</span><div class="mini-track"><div class="mini-fill sky" id="mini-energy"></div></div></div>
          <span class="live-dot" title="桌宠连接状态"></span>
        </div>
      </header>
      <div class="conn-banner" id="conn-banner" hidden>
        ⚠ 未连接到桌宠服务：请确认桌宠正在运行。桌宠每次启动地址/token 都会变化，
        若已重启，请用桌宠启动日志中打印的新地址重新打开本页。
      </div>
      <main class="content" id="view-root"></main>
    </div>
  </div>`;

const nav = document.getElementById("nav")!;
nav.innerHTML = Object.values(routes)
  .map((v) => `<a class="nav-item" data-route="${v.id}" href="#/${v.id}">${v.icon}<span>${v.title}</span></a>`)
  .join("");

const viewRoot = document.getElementById("view-root")!;
const ctx: Ctx = { store, navigate: () => {}, root: viewRoot };
const router = createRouter(viewRoot, routes, ctx);
ctx.navigate = (h) => router.navigate(h);

const dot = document.querySelector<HTMLElement>(".live-dot");
const banner = document.getElementById("conn-banner");
const syncConnected = (v: boolean) => {
  store.setState({ connected: v });
  if (dot) dot.classList.toggle("offline", !v);
  if (banner) banner.hidden = v;
};

const applyStatus = (s: StatusPayload) => {
  store.setState({ ...s, connected: true });
  syncConnected(true);
};

// 断线自愈：连接失败时每 3s 重试一次 status，桌宠（同 token）恢复后自动上线
let retryTimer: number | undefined;
const startRetry = () => {
  if (retryTimer !== undefined) return;
  retryTimer = window.setInterval(() => {
    api.getStatus().then(applyStatus).catch(() => { /* 继续重试 */ });
  }, 3000);
};
const stopRetry = () => {
  if (retryTimer !== undefined) {
    window.clearInterval(retryTimer);
    retryTimer = undefined;
  }
};

const onConnected = () => {
  syncConnected(true);
  stopRetry();
};
const onDisconnected = () => {
  syncConnected(false);
  startRetry();
};

const closeStream = openStatusStream(
  (s) => {
    applyStatus(s);
    onConnected();
  },
  () => onDisconnected(),
);
window.addEventListener("beforeunload", () => closeStream());

api
  .getStatus()
  .then((s) => {
    applyStatus(s);
    onConnected();
  })
  .catch(() => onDisconnected());

const syncMini = () => {
  const s = store.getState();
  const h = document.getElementById("mini-hunger");
  const e = document.getElementById("mini-energy");
  if (h) h.style.width = `${s.hunger}%`;
  if (e) e.style.width = `${s.energy}%`;
};
syncMini();
store.subscribe(syncMini);
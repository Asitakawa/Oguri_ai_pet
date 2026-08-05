import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import { createStore, initialMockState } from "./store";
import { createRouter } from "./router";
import { routes, type Ctx } from "./views";

const store = createStore(initialMockState);
const app = document.getElementById("app");
if (!app) throw new Error("#app not found");

app.innerHTML = `
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar-brand"><span class="brand-dot"></span><span>小栗帽管理面板</span></div>
      <nav class="nav" id="nav"></nav>
      <div class="sidebar-foot">v0.1 · 阶段 1</div>
    </aside>
    <div class="main">
      <header class="topbar">
        <h1 id="topbar-title">仪表盘</h1>
        <div class="topbar-status">
          <div class="mini-bar"><span>饱腹</span><div class="mini-track"><div class="mini-fill rose" id="mini-hunger"></div></div></div>
          <div class="mini-bar"><span>活力</span><div class="mini-track"><div class="mini-fill sky" id="mini-energy"></div></div></div>
          <span class="live-dot" title="桌宠在线（阶段 1 mock）"></span>
        </div>
      </header>
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

const syncMini = () => {
  const s = store.getState().status;
  const h = document.getElementById("mini-hunger");
  const e = document.getElementById("mini-energy");
  if (h) h.style.width = `${s.hunger}%`;
  if (e) e.style.width = `${s.energy}%`;
};
syncMini();
store.subscribe(syncMini);
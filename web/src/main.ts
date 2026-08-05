import "./styles/tokens.css";
import "./styles/base.css";

const app = document.getElementById("app");
if (app) {
  app.innerHTML = `
    <div class="boot">
      <div class="boot-title">小栗帽 · 管理面板</div>
      <div class="boot-sub">阶段 0 骨架就绪 · 阶段 1 将接入布局与仪表盘</div>
    </div>
  `;
}
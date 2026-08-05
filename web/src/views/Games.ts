import type { View } from "./types";

export const Games: View = {
  id: "games",
  title: "游戏",
  icon: "🎮",
  render() {
    return `
    <div class="view view-placeholder glass-card">
      <h2>🎮 游戏</h2>
      <p>阶段 4 接入：5 个游戏开关 / 启动 / 停止</p>
    </div>`;
  },
};
import type { View } from "./types";

export const Settings: View = {
  id: "settings",
  title: "设置",
  icon: "⚙️",
  render() {
    return `
    <div class="view view-placeholder glass-card">
      <h2>⚙️ 设置</h2>
      <p>阶段 3 接入：API / 宠物大小 / 字体 / 系统间隔 / 重启退出</p>
    </div>`;
  },
};
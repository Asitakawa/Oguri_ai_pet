import type { View } from "./types";

export const Chat: View = {
  id: "chat",
  title: "聊天",
  icon: "💬",
  render() {
    return `
    <div class="view view-placeholder glass-card">
      <h2>💬 聊天</h2>
      <p>阶段 3 接入：历史时间线 / 搜索 / 对话 / 清空 / 导出</p>
    </div>`;
  },
};
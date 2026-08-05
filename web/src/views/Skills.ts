import type { View } from "./types";

export const Skills: View = {
  id: "skills",
  title: "技能",
  icon: "⚡",
  render() {
    return `
    <div class="view view-placeholder glass-card">
      <h2>⚡ 技能</h2>
      <p>阶段 4 接入：技能详细设置（参数表 / SKILL.md / 测试执行 / 导入删除）</p>
    </div>`;
  },
};
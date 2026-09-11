/** HTML 文本/属性转义。插入 innerHTML 的任何动态字符串都必须过这里。 */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 与 escapeHtml 等价；用于属性值位置，语义更明确。 */
export function escapeAttr(s: string): string {
  return escapeHtml(s);
}

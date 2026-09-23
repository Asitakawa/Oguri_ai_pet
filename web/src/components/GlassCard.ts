import { escapeHtml } from "../utils";

export interface CardOpts {
  className?: string;
}

/** 卡片：标题只有文字，不放图标 */
export function cardHTML(title: string, body: string, opts: CardOpts = {}): string {
  return `
  <section class="glass-card ${opts.className ?? ""}">
    <header class="card-head">
      <h3>${escapeHtml(title)}</h3>
    </header>
    <div class="card-body">${body}</div>
  </section>`;
}

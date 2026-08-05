export interface CardOpts {
  icon?: string;
  className?: string;
}

export function cardHTML(title: string, body: string, opts: CardOpts = {}): string {
  return `
  <section class="glass-card ${opts.className ?? ""}">
    <header class="card-head">
      ${opts.icon ? `<span class="card-icon">${opts.icon}</span>` : ""}
      <h3>${title}</h3>
    </header>
    <div class="card-body">${body}</div>
  </section>`;
}
const R = 42;
const CIRC = 2 * Math.PI * R;

export interface RingOpts {
  id: string;
  label: string;
  pct: number;
  /** CSS 变量名，必须是实色，如 "--ring-hunger" */
  color: string;
}

/** 状态环：只有弧线 + 百分比数字 + 文字标签，不放图标 */
export function ringHTML(o: RingOpts): string {
  const off = CIRC * (1 - o.pct / 100);
  return `
  <div class="ring" id="${o.id}-wrap">
    <svg viewBox="0 0 100 100" class="ring-svg">
      <circle class="ring-track" cx="50" cy="50" r="${R}"/>
      <circle class="ring-bar" id="${o.id}" cx="50" cy="50" r="${R}"
        stroke="var(${o.color})" stroke-dasharray="${CIRC}" stroke-dashoffset="${off}"/>
    </svg>
    <div class="ring-center">
      <div class="ring-pct" id="${o.id}-pct">${Math.round(o.pct)}%</div>
    </div>
    <div class="ring-label">${o.label}</div>
  </div>`;
}

export function ringUpdate(id: string, pct: number): void {
  const bar = document.getElementById(id) as SVGCircleElement | null;
  const txt = document.getElementById(`${id}-pct`);
  if (bar) bar.style.strokeDashoffset = String(CIRC * (1 - pct / 100));
  if (txt) txt.textContent = `${Math.round(pct)}%`;
}

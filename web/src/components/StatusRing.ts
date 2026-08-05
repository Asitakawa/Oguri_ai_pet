const R = 42;
const CIRC = 2 * Math.PI * R;

export interface RingOpts {
  id: string;
  label: string;
  icon: string;
  pct: number;
  color: string; // CSS 变量名，如 "--c-rose"
}

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
      <div class="ring-icon">${o.icon}</div>
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
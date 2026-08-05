import type { Ctx, View } from "./views/types";

export interface Router {
  navigate(hash: string): void;
  refresh(): void;
}

export function createRouter(
  root: HTMLElement,
  routes: Record<string, View>,
  ctx: Ctx,
): Router {
  let mounted: View | null = null;

  const resolve = (): string => {
    const h = location.hash.replace(/^#\/?/, "");
    return h in routes ? h : "dashboard";
  };

  const render = () => {
    const id = resolve();
    const view = routes[id];
    if (mounted !== view) {
      mounted?.unmount?.(ctx);
      mounted = view;
    }
    root.innerHTML = view.render(ctx);
    view.mount?.(ctx);
    document.querySelectorAll<HTMLElement>("[data-route]").forEach((el) => {
      el.classList.toggle("active", el.dataset.route === id);
    });
    const titleEl = document.getElementById("topbar-title");
    if (titleEl) titleEl.textContent = view.title;
  };

  window.addEventListener("hashchange", render);
  render();

  return {
    navigate: (hash: string) => {
      if (location.hash === `#/${hash}`) render();
      else location.hash = `#/${hash}`;
    },
    refresh: render,
  };
}
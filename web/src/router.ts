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
  // 每次 render 递增：await 之后用它判断"我这一轮是否还是最新的"
  let epoch = 0;

  const resolve = (): string => {
    const h = location.hash.replace(/^#\/?/, "");
    return h in routes ? h : "dashboard";
  };

  const render = async (): Promise<void> => {
    const myEpoch = ++epoch;
    const id = resolve();
    const view = routes[id];
    if (!view) return;

    // 必须在替换 DOM 之前卸载：同一个视图也可能被重复挂载
    // （初始加载无 hash，点侧栏「仪表盘」会命中同 hash 分支），
    // 不卸载就会泄漏 EventSource / store 订阅
    if (mounted) {
      try {
        await mounted.unmount?.(ctx);
      } catch (e) {
        console.error(`[router] ${mounted.id} unmount 失败`, e);
      }
    }
    // 卸载期间用户又跳走了：本轮作废，由最新一轮负责渲染
    if (myEpoch !== epoch) return;

    mounted = view;
    root.innerHTML = view.render(ctx);

    document.querySelectorAll<HTMLElement>("[data-route]").forEach((el) => {
      el.classList.toggle("active", el.dataset.route === id);
    });
    const titleEl = document.getElementById("topbar-title");
    if (titleEl) titleEl.textContent = view.title;

    try {
      await view.mount?.(ctx);
    } catch (e) {
      // mount 可以是 async；不 catch 的话这里只会变成控制台里的
      // unhandled rejection，界面没有任何反馈
      console.error(`[router] ${view.id} mount 失败`, e);
    }
  };

  const scheduleRender = (): void => {
    void render();
  };

  window.addEventListener("hashchange", scheduleRender);
  scheduleRender();

  return {
    navigate: (hash: string) => {
      if (location.hash === `#/${hash}`) scheduleRender();
      else location.hash = `#/${hash}`;
    },
    refresh: scheduleRender,
  };
}

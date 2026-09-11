import type { Store } from "../store";

export interface Ctx {
  store: Store;
  navigate: (hash: string) => void;
  root: HTMLElement;
}

export interface View {
  id: string;
  title: string;
  icon: string;
  render(ctx: Ctx): string;
  /** 可以是 async；router 会 await 并捕获 rejection（不会静默吞掉） */
  mount?(ctx: Ctx): void | Promise<void>;
  unmount?(ctx: Ctx): void | Promise<void>;
}
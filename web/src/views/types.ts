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
  mount?(ctx: Ctx): void;
  unmount?(ctx: Ctx): void;
}
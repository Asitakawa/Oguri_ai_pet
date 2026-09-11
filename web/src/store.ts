import type { StatusPayload } from "./api/types";

export interface AppState extends StatusPayload {
  connected: boolean;
}

export const initialState: AppState = {
  hunger: 50,
  energy: 50,
  chatRounds: 0,
  uptimeSec: 0,
  enabledSkills: 0,
  totalSkills: 0,
  sysCpu: null,
  sysMemMB: null,
  petOnline: false,
  companion: null,
  connected: false,
};

export type Listener = () => void;

export interface Store {
  getState(): AppState;
  setState(patch: Partial<AppState>): void;
  subscribe(fn: Listener): () => void;
}

export function createStore(initial: AppState): Store {
  let state = initial;
  const listeners = new Set<Listener>();
  return {
    getState: () => state,
    setState: (patch) => {
      state = { ...state, ...patch };
      listeners.forEach((fn) => fn());
    },
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
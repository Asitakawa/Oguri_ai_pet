export interface PetStatus {
  hunger: number;
  energy: number;
}

export interface AppState {
  status: PetStatus;
  chatRounds: number;
  uptimeSec: number;
  enabledSkills: number;
  totalSkills: number;
  sysCpu: number;
  sysMemGB: number;
}

// 阶段 1：mock 初始状态；阶段 2 起由真实 API 填充
export const initialMockState: AppState = {
  status: { hunger: 72, energy: 55 },
  chatRounds: 128,
  uptimeSec: 3 * 3600 + 42 * 60,
  enabledSkills: 2,
  totalSkills: 2,
  sysCpu: 8,
  sysMemGB: 3.2,
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
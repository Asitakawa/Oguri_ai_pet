import type { PetStatus } from "./types";

// 阶段 1：mock 实现；阶段 2 接入真实 REST API
export const api = {
  async getStatus(): Promise<PetStatus> {
    return { hunger: 72, energy: 55 };
  },
  async feed(): Promise<PetStatus> {
    const s = await api.getStatus();
    return {
      hunger: Math.min(100, s.hunger + 30),
      energy: Math.min(100, s.energy + 5),
    };
  },
};
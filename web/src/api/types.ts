export interface PetStatus {
  hunger: number;
  energy: number;
}

export interface StatusPayload {
  hunger: number;
  energy: number;
  chatRounds: number;
  uptimeSec: number;
  enabledSkills: number;
  totalSkills: number;
  sysCpu: number | null;
  sysMemMB: number | null;
  petOnline: boolean;
}

export interface ChatMessage {
  role: "user" | "pet";
  content: string;
  timestamp: string;
}

export interface GameInfo {
  key: string;
  name: string;
  desc: string;
  enabled: boolean;
  active: boolean;
}

export interface SkillInfo {
  name: string;
  description: string;
  enabled: boolean;
  dirname: string;
}
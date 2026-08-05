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
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ProviderInfo {
  key: string;
  name: string;
  models: string[];
}

export interface SettingsPayload {
  api: {
    provider: string;
    model: string;
    keyConfigured: boolean;
    providers: ProviderInfo[];
    models: string[];
  };
  system: {
    minAutoReply: number;
    maxAutoReply: number;
    presetMin: number;
    presetMax: number;
    memoryRounds: number;
  };
  font: {
    family: string;
    size: number;
    sizeMin: number;
    sizeMax: number;
    families: string[];
  };
  pet: {
    scale: number;
    minScale: number;
    maxScale: number;
  };
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
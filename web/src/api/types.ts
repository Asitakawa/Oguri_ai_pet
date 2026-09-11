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
  /** 跨会话累积的陪伴统计；桌宠未提供时为 null */
  companion: CompanionStats | null;
}

export interface CompanionStats {
  daysTogether: number;
  totalHours: number;
  sessionSeconds: number;
  sessions: number;
  feedCount: number;
  chatRounds: number;
  dragCount: number;
  maxFlyMeters: number;
  gamesPlayed: number;
  factsLearned: number;
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
    /** 以下三项由后端下发，避免前端硬编码与后端钳制范围漂移 */
    memoryRoundsMin: number;
    memoryRoundsMax: number;
    memoryRoundsDefault: number;
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
  systemExtra: {
    autostart: boolean;
    autostartSupported: boolean;
    dataDir: string;
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
export interface SkillParam {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

export interface SkillDetail extends SkillInfo {
  parameters: SkillParam[];
  skillMd: string;
}
export interface LogPayload {
  lines: string[];
  offset: number;
}

export interface MemoryFact {
  id: string;
  text: string;
  source: string;
  created_at: string;
}

export interface MemoryPayload {
  available: boolean;
  enabled: boolean;
  facts: MemoryFact[];
  maxFacts?: number;
}

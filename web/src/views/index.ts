import type { View } from "./types";
import { Dashboard } from "./Dashboard";
import { Chat } from "./Chat";
import { Games } from "./Games";
import { Skills } from "./Skills";
import { Settings } from "./Settings";

export const routes: Record<string, View> = {
  dashboard: Dashboard,
  chat: Chat,
  games: Games,
  skills: Skills,
  settings: Settings,
};

export type { Ctx, View } from "./types";
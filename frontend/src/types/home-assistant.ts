export interface HomeAssistantConnection {
  subscribeMessage(
    callback: (message: unknown) => void,
    message: Record<string, unknown>,
  ): Promise<() => void>;
}

export interface HomeAssistantLike {
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  connection: HomeAssistantConnection;
  locale: { language: string };
  config: { unit_system: { temperature: "°C" | "°F" } };
}

export interface IntelligentClimatePanelEntry {
  entry_id: string;
  title: string;
}

export interface IntelligentClimatePanelConfig {
  api_version: number;
  frontend_version: string;
  entries: IntelligentClimatePanelEntry[];
}

export interface HomeAssistantPanelInfo {
  config: IntelligentClimatePanelConfig;
}

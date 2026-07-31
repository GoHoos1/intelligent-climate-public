export type TemperatureUnitPreference =
  "home_assistant" | "fahrenheit" | "celsius";

const STORAGE_KEY = "intelligent-climate.temperature-unit";

export function readTemperatureUnitPreference(): TemperatureUnitPreference {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === "fahrenheit" || value === "celsius") {
      return value;
    }
  } catch {
    // Private browsing and hardened browsers may deny local storage.
  }
  return "home_assistant";
}

export function writeTemperatureUnitPreference(
  value: TemperatureUnitPreference,
): void {
  try {
    if (value === "home_assistant") {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, value);
    }
  } catch {
    // The in-memory selection remains effective for this panel session.
  }
}

export function resolveTemperatureUnit(
  preference: TemperatureUnitPreference,
  homeAssistantUnit: "°C" | "°F",
): "°C" | "°F" {
  if (preference === "fahrenheit") {
    return "°F";
  }
  if (preference === "celsius") {
    return "°C";
  }
  return homeAssistantUnit;
}

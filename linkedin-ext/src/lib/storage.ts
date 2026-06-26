import { DEFAULT_SETTINGS, ExtSettings } from "./types";

const SETTINGS_KEY = "settings";

export async function getSettings(): Promise<ExtSettings> {
  const raw = await chrome.storage.local.get(SETTINGS_KEY);
  const stored = (raw[SETTINGS_KEY] as Partial<ExtSettings>) ?? {};
  return { ...DEFAULT_SETTINGS, ...stored };
}

export async function setSettings(patch: Partial<ExtSettings>): Promise<ExtSettings> {
  const current = await getSettings();
  const next = { ...current, ...patch };
  await chrome.storage.local.set({ [SETTINGS_KEY]: next });
  return next;
}

export async function resetSettings(): Promise<ExtSettings> {
  await chrome.storage.local.set({ [SETTINGS_KEY]: DEFAULT_SETTINGS });
  return { ...DEFAULT_SETTINGS };
}

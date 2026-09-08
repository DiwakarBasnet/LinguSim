export type TargetLanguage = "English" | "German";

const STORAGE_KEY = "speakquest:target_language";

type Listener = () => void;
const listeners = new Set<Listener>();

export function getStoredLanguage(): TargetLanguage {
  if (typeof window === "undefined") return "English";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "German" ? "German" : "English";
  } catch {
    return "English";
  }
}

export function getServerLanguage(): TargetLanguage {
  return "English";
}

export function setStoredLanguage(language: TargetLanguage): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // localStorage unavailable (private mode, etc.) — selection just won't persist.
  }
  listeners.forEach((listener) => listener());
}

/** For useSyncExternalStore — keeps components in sync when the language
 * preference changes (e.g. set from this same tab's UI). */
export function subscribeToLanguage(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

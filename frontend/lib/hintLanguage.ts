/**
 * The "hint language" — whichever language the learner understands best,
 * chosen once up front. Independent of the target language being practiced
 * (see lib/language.ts): a learner practicing German or Japanese still
 * wants live hints and grammar corrections explained in a language they
 * actually understand, not the one they're trying to learn.
 */
export type HintLanguage = "English" | "German" | "Japanese";

const STORAGE_KEY = "speakquest:hint_language";
export const HINT_LANGUAGES: HintLanguage[] = ["English", "German", "Japanese"];
export const HINT_LANGUAGE_LABEL: Record<HintLanguage, string> = {
  English: "English",
  German: "Deutsch",
  Japanese: "日本語",
};

type Listener = () => void;
const listeners = new Set<Listener>();

/** null means the learner hasn't picked one yet — distinct from any real language. */
export function getStoredHintLanguage(): HintLanguage | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return (HINT_LANGUAGES as string[]).includes(stored ?? "") ? (stored as HintLanguage) : null;
  } catch {
    return null;
  }
}

export function getServerHintLanguage(): HintLanguage | null {
  return null;
}

export function setStoredHintLanguage(language: HintLanguage): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // localStorage unavailable (private mode, etc.) — selection just won't persist.
  }
  listeners.forEach((listener) => listener());
}

/** For useSyncExternalStore — keeps components in sync when the preference
 * changes (e.g. set from this same tab's onboarding prompt). */
export function subscribeToHintLanguage(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

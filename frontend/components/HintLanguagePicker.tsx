"use client";

import { useSyncExternalStore } from "react";
import {
  getServerHintLanguage,
  getStoredHintLanguage,
  setStoredHintLanguage,
  subscribeToHintLanguage,
  HINT_LANGUAGES,
  HINT_LANGUAGE_LABEL,
  type HintLanguage,
} from "@/lib/hintLanguage";

/** Compact header control for changing the hint language after the initial
 * HintLanguageGate prompt. */
export default function HintLanguagePicker() {
  const hintLanguage = useSyncExternalStore(
    subscribeToHintLanguage,
    getStoredHintLanguage,
    getServerHintLanguage,
  );

  return (
    <label className="ml-auto flex items-center gap-1.5 text-xs text-black/50 dark:text-white/50">
      Hints in
      <select
        value={hintLanguage ?? ""}
        onChange={(e) => setStoredHintLanguage(e.target.value as HintLanguage)}
        className="rounded-md border border-black/10 bg-transparent px-1.5 py-1 text-xs dark:border-white/10"
      >
        {hintLanguage === null && <option value="" disabled />}
        {HINT_LANGUAGES.map((lang) => (
          <option key={lang} value={lang}>
            {HINT_LANGUAGE_LABEL[lang]}
          </option>
        ))}
      </select>
    </label>
  );
}

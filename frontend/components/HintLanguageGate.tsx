"use client";

import { useSyncExternalStore } from "react";
import {
  getServerHintLanguage,
  getStoredHintLanguage,
  setStoredHintLanguage,
  subscribeToHintLanguage,
  HINT_LANGUAGES,
  HINT_LANGUAGE_LABEL,
} from "@/lib/hintLanguage";

/**
 * Blocks the app behind a one-time "which language do you understand best?"
 * prompt until a hint language is chosen, then gets out of the way. The
 * preference persists (localStorage) so this never shows again on this
 * device unless cleared.
 */
export default function HintLanguageGate({ children }: { children: React.ReactNode }) {
  const hintLanguage = useSyncExternalStore(
    subscribeToHintLanguage,
    getStoredHintLanguage,
    getServerHintLanguage,
  );

  return (
    <>
      {children}
      {hintLanguage === null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6">
          <div className="w-full max-w-sm rounded-lg border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-neutral-900">
            <h2 className="text-lg font-semibold">Which language do you understand best?</h2>
            <p className="mt-2 text-sm text-black/60 dark:text-white/60">
              During a simulation, hints and grammar corrections will be given in this language.
              You can change it later from the header.
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {HINT_LANGUAGES.map((lang) => (
                <button
                  key={lang}
                  onClick={() => setStoredHintLanguage(lang)}
                  className="rounded-md border border-black/10 px-4 py-2 text-left text-sm hover:border-black/30 dark:border-white/10 dark:hover:border-white/30"
                >
                  {HINT_LANGUAGE_LABEL[lang]}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

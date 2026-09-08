"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import {
  getServerLanguage,
  getStoredLanguage,
  setStoredLanguage,
  subscribeToLanguage,
  type TargetLanguage,
} from "@/lib/language";
import type { Difficulty, Scenario } from "@/lib/types";

const DIFFICULTY_ORDER: Difficulty[] = ["beginner", "intermediate", "advanced"];
const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
const LANGUAGES: TargetLanguage[] = ["English", "German"];

function groupByDifficulty(scenarios: Scenario[]): Record<Difficulty, Scenario[]> {
  const grouped: Record<Difficulty, Scenario[]> = { beginner: [], intermediate: [], advanced: [] };
  for (const scenario of scenarios) {
    grouped[scenario.difficulty].push(scenario);
  }
  return grouped;
}

export default function ScenarioBrowser({ scenarios }: { scenarios: Scenario[] }) {
  const language = useSyncExternalStore(subscribeToLanguage, getStoredLanguage, getServerLanguage);

  const handleSelect = (next: TargetLanguage) => {
    setStoredLanguage(next);
  };

  const filtered = scenarios.filter((s) => s.target_language === language);
  const grouped = groupByDifficulty(filtered);

  return (
    <div className="flex flex-col gap-8">
      <div className="inline-flex self-start rounded-full border border-black/10 p-1 dark:border-white/10">
        {LANGUAGES.map((lang) => (
          <button
            key={lang}
            onClick={() => handleSelect(lang)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              language === lang
                ? "bg-black text-white dark:bg-white dark:text-black"
                : "text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white"
            }`}
          >
            {lang === "German" ? "Deutsch" : "English"}
          </button>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-black/60 dark:text-white/60">
          No {language} missions available yet.
        </p>
      )}

      {DIFFICULTY_ORDER.filter((d) => grouped[d].length > 0).map((difficulty) => (
        <section key={difficulty} className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            {DIFFICULTY_LABEL[difficulty]}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {grouped[difficulty].map((scenario) => (
              <Link
                key={scenario.id}
                href={`/simulate/${scenario.id}`}
                className="flex flex-col gap-2 rounded-lg border border-black/10 p-4 transition hover:border-black/30 dark:border-white/10 dark:hover:border-white/30"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{scenario.title}</h3>
                  <span className="text-xs text-black/50 dark:text-white/50">
                    {scenario.duration_minutes} min
                  </span>
                </div>
                <p className="text-sm text-black/60 dark:text-white/60">{scenario.description}</p>
                {scenario.possible_events.length > 0 && (
                  <p className="text-xs text-black/40 dark:text-white/40">
                    ⚡ May throw up to {scenario.possible_events.length} complication
                    {scenario.possible_events.length === 1 ? "" : "s"} mid-conversation
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {[...scenario.vocabulary_themes, ...scenario.grammar_themes].map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full bg-black/5 px-2 py-0.5 text-xs text-black/60 dark:bg-white/10 dark:text-white/60"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

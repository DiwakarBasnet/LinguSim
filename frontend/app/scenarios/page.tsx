import Link from "next/link";
import { fetchScenarios } from "@/lib/api";
import type { Difficulty, Scenario } from "@/lib/types";

const DIFFICULTY_ORDER: Difficulty[] = ["beginner", "intermediate", "advanced"];
const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

function groupByDifficulty(scenarios: Scenario[]): Record<Difficulty, Scenario[]> {
  const grouped: Record<Difficulty, Scenario[]> = {
    beginner: [],
    intermediate: [],
    advanced: [],
  };
  for (const scenario of scenarios) {
    grouped[scenario.difficulty].push(scenario);
  }
  return grouped;
}

export default async function ScenariosPage() {
  let scenarios: Scenario[] = [];
  let loadError: string | null = null;
  try {
    scenarios = await fetchScenarios();
  } catch {
    loadError = "Couldn't reach the backend. Is it running on the expected port?";
  }

  const grouped = groupByDifficulty(scenarios);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Choose a scenario</h1>
        <p className="mt-1 text-black/60 dark:text-white/60">
          Pick a real-world situation to practice. The AI adapts to how you do.
        </p>
      </div>

      {loadError && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {loadError}
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

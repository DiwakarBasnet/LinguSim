import { fetchScenarios } from "@/lib/api";
import ScenarioBrowser from "@/components/ScenarioBrowser";
import type { Scenario } from "@/lib/types";

export default async function ScenariosPage() {
  let scenarios: Scenario[] = [];
  let loadError: string | null = null;
  try {
    scenarios = await fetchScenarios();
  } catch {
    loadError = "Couldn't reach the backend. Is it running on the expected port?";
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Choose a mission</h1>
        <p className="mt-1 text-black/60 dark:text-white/60">
          Pick a real-world situation to survive. The conversation adapts to what you say —
          expect it to throw you a curveball.
        </p>
      </div>

      {loadError ? (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {loadError}
        </p>
      ) : (
        <ScenarioBrowser scenarios={scenarios} />
      )}
    </div>
  );
}

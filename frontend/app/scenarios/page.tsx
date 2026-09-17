import { fetchScenarios } from "@/lib/api";
import ScenarioBrowser from "@/components/ScenarioBrowser";
import LoadErrorBanner from "@/components/LoadErrorBanner";
import type { Scenario } from "@/lib/types";

export default async function ScenariosPage() {
  let scenarios: Scenario[] = [];
  let loadError: string | null = null;
  try {
    scenarios = await fetchScenarios();
  } catch {
    loadError = "Couldn't load missions.";
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

      {loadError ? <LoadErrorBanner message={loadError} /> : <ScenarioBrowser scenarios={scenarios} />}
    </div>
  );
}

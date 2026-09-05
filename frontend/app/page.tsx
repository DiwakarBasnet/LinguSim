import Link from "next/link";
import { fetchProfile, fetchScenario, fetchSessions } from "@/lib/api";
import { computeStreak, overallScoreTrend, topWeaknesses } from "@/lib/dashboard";

export default async function DashboardPage() {
  const [profile, sessions] = await Promise.all([fetchProfile(), fetchSessions()]);

  if (profile.completed_scenarios === 0) {
    return (
      <div className="flex flex-col gap-8">
        <Header />
        <div className="rounded-lg border border-black/10 p-6 dark:border-white/10">
          <h2 className="font-medium">No sessions yet</h2>
          <p className="mt-1 text-sm text-black/60 dark:text-white/60">
            Your grammar, vocabulary, and fluency profile builds up after your first
            scenario. Weaknesses and a recommended next scenario will show up here
            once you have practice history.
          </p>
          <Link
            href="/scenarios"
            className="mt-4 inline-block rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
          >
            Start a scenario
          </Link>
        </div>
      </div>
    );
  }

  const streak = computeStreak(sessions);
  const weaknesses = topWeaknesses(profile);
  const trend = overallScoreTrend(sessions);
  const recent = sessions.slice(-3).reverse();
  const recommended = profile.recommended_scenario_id
    ? await fetchScenario(profile.recommended_scenario_id).catch(() => null)
    : null;

  return (
    <div className="flex flex-col gap-8">
      <Header />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Target language" value={profile.target_language} />
        <Stat label="Level" value={profile.level} />
        <Stat label="Streak" value={`${streak} day${streak === 1 ? "" : "s"}`} />
        <Stat label="Scenarios completed" value={String(profile.completed_scenarios)} />
      </div>

      {trend.length > 0 && (
        <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Overall progress
          </h2>
          <p className="mt-2 font-mono text-sm">{trend.join("% → ")}%</p>
          <Link href="/progress" className="mt-2 inline-block text-sm underline">
            View full progress
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Weaknesses
          </h2>
          {weaknesses.length === 0 ? (
            <p className="mt-2 text-sm text-black/60 dark:text-white/60">
              No consistent weak spots yet — keep practicing.
            </p>
          ) : (
            <ul className="mt-2 flex flex-col gap-1.5 text-sm">
              {weaknesses.map((w) => (
                <li key={w.theme} className="flex items-center justify-between">
                  <span className="capitalize">{w.theme}</span>
                  <span className="text-black/50 dark:text-white/50">Needs practice</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Recent practice
          </h2>
          <ul className="mt-2 flex flex-col gap-1.5 text-sm">
            {recent.map((s) => (
              <li key={s.id} className="flex items-center justify-between">
                <span>{s.scenario_title}</span>
                <span className="text-black/50 dark:text-white/50">
                  {Math.round(s.evaluation.overall_score / 10)}/10
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-black/10 p-4 dark:border-white/10">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Recommended next
          </h2>
          <p className="mt-1 text-sm">
            {recommended ? recommended.title : "Pick any scenario to keep going."}
          </p>
        </div>
        <Link
          href={recommended ? `/simulate/${recommended.id}` : "/scenarios"}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80"
        >
          Start scenario
        </Link>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-black/60 dark:text-white/60">
        Practice a real-world scenario, get evaluated, and see what to work on next.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
      <div className="text-xs text-black/50 dark:text-white/50">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}

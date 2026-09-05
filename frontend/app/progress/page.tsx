import { fetchProfile, fetchSessions } from "@/lib/api";
import ProgressChart from "@/components/ProgressChart";

export default async function ProgressPage() {
  const [profile, sessions] = await Promise.all([fetchProfile(), fetchSessions()]);

  const byDifficulty = sessions.reduce<Record<string, number>>((acc, s) => {
    acc[s.difficulty] = (acc[s.difficulty] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Progress</h1>
        <p className="mt-1 text-black/60 dark:text-white/60">
          Grammar, vocabulary, fluency, and hesitation across every completed session.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
          <div className="text-xs text-black/50 dark:text-white/50">Completed scenarios</div>
          <div className="mt-1 text-lg font-semibold">{profile.completed_scenarios}</div>
        </div>
        {(["beginner", "intermediate", "advanced"] as const).map((difficulty) => (
          <div key={difficulty} className="rounded-lg border border-black/10 p-4 dark:border-white/10">
            <div className="text-xs capitalize text-black/50 dark:text-white/50">{difficulty}</div>
            <div className="mt-1 text-lg font-semibold">{byDifficulty[difficulty] ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
        <ProgressChart sessions={sessions} />
      </div>

      <p className="text-xs text-black/40 dark:text-white/40">
        Pronunciation isn&apos;t tracked here — see the note on the feedback screen for why.
      </p>
    </div>
  );
}

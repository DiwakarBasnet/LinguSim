import type { LearnerProfile, SessionSummary } from "./types";

/** Consecutive-day streak ending today or yesterday (a day off doesn't
 * retroactively erase the streak, but it does stop counting once broken). */
export function computeStreak(sessions: SessionSummary[]): number {
  if (sessions.length === 0) return 0;

  const days = new Set(
    sessions.map((s) => new Date(s.created_at).toISOString().slice(0, 10))
  );

  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);

  let streak = 0;
  const cursor = new Date(today);
  // Allow the streak to still "count" if today has no session yet, as long
  // as yesterday does — otherwise a streak would reset to 0 every morning
  // before the learner has practiced.
  if (!days.has(cursor.toISOString().slice(0, 10))) {
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }

  while (days.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }

  return streak;
}

export interface WeaknessEntry {
  theme: string;
  score: number;
}

const WEAKNESS_THRESHOLD = 0.7;

export function topWeaknesses(profile: LearnerProfile, limit = 3): WeaknessEntry[] {
  const combined: Record<string, number> = { ...profile.grammar, ...profile.vocabulary };
  // Handling surprises isn't a grammar/vocab theme, but it's exactly the
  // kind of weakness this app is built to surface — treat it the same way.
  if (profile.communication_recovery !== null) {
    combined["handling surprises"] = profile.communication_recovery;
  }
  return Object.entries(combined)
    .map(([theme, score]) => ({ theme, score }))
    .filter((entry) => entry.score < WEAKNESS_THRESHOLD)
    .sort((a, b) => a.score - b.score)
    .slice(0, limit);
}

export function overallScoreTrend(sessions: SessionSummary[], limit = 5): number[] {
  return sessions.slice(-limit).map((s) => Math.round(s.evaluation.overall_score));
}

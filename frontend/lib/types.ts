export type Difficulty = "beginner" | "intermediate" | "advanced";

export interface DifficultyModifier {
  trigger: "struggling" | "excelling";
  description: string;
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  target_language: "English" | "German";
  difficulty: Difficulty;
  duration_minutes: number;
  ai_role: string;
  learner_role: string;
  objectives: string[];
  vocabulary_themes: string[];
  grammar_themes: string[];
  possible_events: string[];
  success_criteria: string[];
  difficulty_modifiers: DifficultyModifier[];
}

export type Speaker = "learner" | "ai";

export interface Turn {
  turn_index: number;
  speaker: Speaker;
  text: string;
}

export interface Transcript {
  scenario_id: string;
  turns: Turn[];
}

export interface EvaluationResult {
  overall_score: number;
  grammar: number;
  vocabulary: number;
  fluency: number;
  hesitation: number;
  task_completion: number;
  conversation_handling: number;
  weaknesses: string[];
  strengths: string[];
}

export interface LearnerProfile {
  target_language: string;
  level: string;
  grammar: Record<string, number>;
  vocabulary: Record<string, number>;
  fluency: number | null;
  hesitation: number | null;
  // Never populated: evaluation only ever sees a text transcript, which
  // carries no phoneme/acoustic signal — see backend LearnerProfileRecord.
  pronunciation: number | null;
  completed_scenarios: number;
  updated_at: string | null;
  recommended_scenario_id: string | null;
}

export interface SessionSummary {
  id: string;
  scenario_id: string;
  scenario_title: string;
  difficulty: Difficulty;
  evaluation: EvaluationResult;
  created_at: string;
}

export interface SessionEndPayload {
  type: "session_end";
  transcript: Transcript;
  session_id?: string;
  evaluation?: EvaluationResult;
  profile?: LearnerProfile;
  recommended_scenario_id?: string;
  error?: string;
}

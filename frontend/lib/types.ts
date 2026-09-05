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

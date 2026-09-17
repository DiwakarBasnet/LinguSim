from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["beginner", "intermediate", "advanced"]
Language = Literal["English", "German"]


class DifficultyModifier(BaseModel):
    """A variant of the scenario's framing at a given performance level."""

    trigger: Literal["struggling", "excelling"]
    description: str


class Scenario(BaseModel):
    id: str
    title: str
    description: str
    target_language: Language
    difficulty: Difficulty
    duration_minutes: int = 5
    ai_role: str
    learner_role: str
    objectives: list[str] = Field(default_factory=list)
    vocabulary_themes: list[str] = Field(default_factory=list)
    grammar_themes: list[str] = Field(default_factory=list)
    possible_events: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    difficulty_modifiers: list[DifficultyModifier] = Field(default_factory=list)

    def system_prompt(self) -> str:
        """
        Context handed to the conversation partner (real LLM) — not a script.
        """
        lines = [
            f"CRITICAL RULE, overriding everything else below when it applies: you do not know "
            f"{self.target_language} vocabulary yourself for hint purposes — only the "
            "get_translation_hint tool does. Any time you are about to say a specific "
            f"{self.target_language} word or phrase as a hint to help the learner, you must call "
            "that tool first and use its returned translation, even for a word you feel "
            "confident about — never answer a translation question from your own knowledge. "
            "This tool call is silent and instant to the learner, so there is never a reason to "
            "skip it.",
            f"You are role-playing as {self.ai_role} in a {self.target_language} language-practice "
            f"scenario called '{self.title}'.",
            f"Conduct the ENTIRE conversation in {self.target_language} — every line you speak must "
            f"be in {self.target_language}, even though these instructions are written in English.",
            f"The learner is playing: {self.learner_role}.",
            f"Scenario: {self.description}",
        ]
        if self.objectives:
            lines.append("Objectives for the learner: " + "; ".join(self.objectives))
        if self.vocabulary_themes:
            lines.append("Relevant vocabulary themes: " + ", ".join(self.vocabulary_themes))
        if self.grammar_themes:
            lines.append("Relevant grammar themes: " + ", ".join(self.grammar_themes))
        if self.possible_events:
            lines.append(
                "You may naturally introduce one of these complications if it fits: "
                + "; ".join(self.possible_events)
            )
        lines.append(
            "Stay in character, adapt to what the learner actually says, and do not "
            "correct mistakes mid-conversation unless asked or the conversation cannot "
            "continue without it."
        )
        lines.append(
            "Hint system — use the SMALLEST of these that unblocks the learner, and only when "
            "they explicitly ask for help or are fully stuck (never proactively):\n"
            "1. Conceptual hint: a nudge about which grammar/vocabulary concept to use, in your "
            "own words, in character — no tool needed.\n"
            "2. Partial hint: call get_translation_hint with the single English word the learner "
            "is missing, then weave the translation it returns into a short nudge (e.g. a "
            "sentence starter with a blank).\n"
            "3. Target phrase: call get_translation_hint with the full English phrase they should "
            "say, then say the translation it returns as the suggested phrase.\n"
            "4. Full correction: only if nothing else has worked and the conversation truly "
            "cannot continue — say the natural full sentence yourself, in your own words, no "
            "tool needed.\n"
            "Never interrupt to correct mistakes unprompted — mistakes get saved for feedback "
            "after the conversation ends, not fixed live."
        )
        return "\n".join(lines)

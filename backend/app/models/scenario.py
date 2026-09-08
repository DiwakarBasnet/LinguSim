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
        These instructions are always written in English (so scenario authors
        and the Scenario Selection UI stay readable regardless of the
        scenario's target_language), but the conversation itself must happen
        in target_language — so that's stated explicitly rather than left to
        be inferred from the instruction language.
        """
        lines = [
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
        return "\n".join(lines)

from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["beginner", "intermediate", "advanced"]
Language = Literal["English", "German", "Japanese"]

HintLanguage = Literal["English", "German", "Japanese"]


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

    def system_prompt(self, hint_language: str = "English") -> str:
        """
        Context handed to the conversation partner (real LLM) — not a script.

        `hint_language` is whichever language the learner understands best
        (their own preference, selected up front and unrelated to
        target_language) — every hint and grammar correction must be given
        in it, since a hint in a language the learner doesn't understand
        isn't a hint at all.
        """
        lines = [
            f"CRITICAL RULE, overriding everything else below when it applies: you do not know "
            f"{self.target_language} vocabulary yourself for hint purposes — only the "
            "get_translation_hint tool does. Any time you are about to say a specific "
            f"{self.target_language} word or phrase as a hint to help the learner, OR explain a "
            f"{self.target_language} phrase they didn't understand, you must call "
            "that tool first and use its returned translation, even for a word you feel "
            "confident about — never answer a translation question from your own knowledge. "
            "This tool call is silent and instant to the learner, so there is never a reason to "
            "skip it.",
            f"The learner's chosen hint language — the language they understand best — is "
            f"{hint_language}. Every hint and grammar correction you give must be understandable "
            f"to someone who reads {hint_language}, per the hint system and grammar-correction "
            "rules below.",
            f"You are role-playing as {self.ai_role} in a {self.target_language} language-practice "
            f"scenario called '{self.title}'.",
            f"Conduct the ENTIRE conversation in {self.target_language} — every line you speak must "
            f"be in {self.target_language}, EXCEPT when giving a hint or explaining something they didn't understand, which should be spoken in {hint_language}.",
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
            "Stay in character, adapt to what the learner actually says, and never SPEAK a "
            "correction mid-conversation unless asked or the conversation cannot continue "
            "without it — see the silent grammar-correction tool below for how mistakes get "
            "flagged instead."
        )
        lines.append(
            "Hint system — use the SMALLEST of these that unblocks the learner, and only when "
            "they explicitly ask for help or are fully stuck (never proactively):\n"
            f"1. Conceptual hint: a nudge about which grammar/vocabulary concept to use, in "
            f"{hint_language}, in character — no tool needed.\n"
            f"2. Partial hint: call get_translation_hint (direction='into_target') with the single {hint_language} word "
            "the learner is missing, then weave the translation it returns into a short nudge.\n"
            f"3. Target phrase: call get_translation_hint (direction='into_target') with the full {hint_language} phrase "
            "they should say, then say the translation it returns as the suggested phrase.\n"
            f"4. Comprehension hint: if the learner didn't understand what you just said, call get_translation_hint (direction='into_hint') with the {self.target_language} phrase they didn't understand, then tell them the {hint_language} translation.\n"
            "5. Full correction: only if nothing else has worked and the conversation truly "
            "cannot continue — say the natural full sentence yourself, in your own words, no "
            "tool needed.\n"
            "Never interrupt to correct mistakes unprompted — mistakes get saved for feedback "
            "after the conversation ends, not fixed live."
        )
        lines.append(
            "Grammar-correction tool — separate from the hint system above, this runs "
            "continuously in the background, not just when the learner is stuck: any time the "
            f"learner says something with an incorrect {self.target_language} grammar form "
            "(wrong conjugation, wrong particle/preposition, wrong word order, wrong politeness "
            "level, etc.), silently call flag_grammar_correction with a single `note` argument — "
            f"a short correction written entirely in {hint_language}, naming what was wrong and "
            "the correct form (e.g. quote the learner's phrase, then the corrected phrase, then "
            "a one-line reason). Call it at most once per learner turn, only for a real grammar "
            "error, not for style or vocabulary choice. This call is silent and instant to the "
            "learner and is never spoken aloud — it must never change what you actually say back "
            "in character, and it never counts as the live spoken correction the rule above "
            "forbids."
        )
        return "\n".join(lines)

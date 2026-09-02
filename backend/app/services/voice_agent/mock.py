from app.services.voice_agent.base import VoiceAgentSession


class MockVoiceAgentSession(VoiceAgentSession):
    """
    Rule-based conversation partner with zero external calls.

    Not a language model: it walks through the scenario's own objectives and
    possible_events in order, lightly acknowledging what the learner said, so
    the full end-to-end demo loop (turns, transcript, evaluation, profile
    update) is exercisable before ASSEMBLYAI_API_KEY is wired up. Swap
    VOICE_AGENT_PROVIDER to "assemblyai" to replace this with a real,
    adaptive conversation partner without touching the WebSocket protocol
    or the frontend.
    """

    def __init__(self, scenario):
        super().__init__(scenario)
        self._event_index = 0

    async def start(self) -> str:
        return f"({self.scenario.ai_role}) Hello! {self._first_prompt()}"

    def _first_prompt(self) -> str:
        if self.scenario.objectives:
            return f"Let's get started — {self.scenario.objectives[0].lower()}."
        return "Let's get started."

    async def respond(self, learner_text: str) -> str:
        acknowledgement = self._acknowledge(learner_text)
        follow_up = self._next_beat()
        return f"{acknowledgement} {follow_up}".strip()

    def _acknowledge(self, learner_text: str) -> str:
        trimmed = learner_text.strip()
        if not trimmed:
            return "Sorry, I didn't catch that — could you say it again?"
        if len(trimmed.split()) <= 2:
            return "Okay."
        return "Got it, thanks."

    def _next_beat(self) -> str:
        events = self.scenario.possible_events
        objectives = self.scenario.objectives
        beats = events or objectives
        if not beats:
            return "Please continue."
        beat = beats[self._event_index % len(beats)]
        self._event_index += 1
        return beat

from typing import Literal

from pydantic import BaseModel

Speaker = Literal["learner", "ai"]


class Turn(BaseModel):
    turn_index: int
    speaker: Speaker
    text: str


class Transcript(BaseModel):
    scenario_id: str
    turns: list[Turn] = []

    def add(self, speaker: Speaker, text: str) -> Turn:
        turn = Turn(turn_index=len(self.turns), speaker=speaker, text=text)
        self.turns.append(turn)
        return turn

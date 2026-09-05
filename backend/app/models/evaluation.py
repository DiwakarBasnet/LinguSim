from pydantic import BaseModel, Field

# No pronunciation field, deliberately: every evaluator here only ever sees a
# text transcript, which carries no phoneme/acoustic signal. Claiming a
# pronunciation score from that would be fabricating it — see the project's
# pronunciation-honesty requirement. A real pronunciation feature needs a
# dedicated phoneme-analysis input and should be added as its own field
# alongside this model, not folded into "fluency" or invented here.


class EvaluationResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    grammar: int = Field(ge=0, le=100)
    vocabulary: int = Field(ge=0, le=100)
    fluency: int = Field(ge=0, le=100)
    hesitation: int = Field(ge=0, le=100, description="Higher = fewer fillers/hesitations")
    task_completion: int = Field(ge=0, le=100)
    conversation_handling: int = Field(ge=0, le=100)
    weaknesses: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)

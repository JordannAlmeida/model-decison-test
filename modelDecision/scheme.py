from enum import Enum
from typing import Annotated, Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class Type(str, Enum):
    NOUL = "noul"
    CHOICE = "choice"
    SCORE = "score"


# `string | object | array`
Content = str | Dict[str, Any] | List[Any]


# ---------- Request ----------

class NoulCriteria(BaseModel):
    true: Content | None = None
    false: Content | None = None


class NoulQuestion(BaseModel):
    type: Literal[Type.NOUL]
    instructions: Content
    criteria: NoulCriteria | None = None


class ChoiceQuestion(BaseModel):
    type: Literal[Type.CHOICE]
    instructions: Content
    # option name -> description (None for no description), max 255 options
    criteria: Dict[str, Content | None] = Field(max_length=255)


class ScoreQuestion(BaseModel):
    type: Literal[Type.SCORE]
    instructions: Content
    # ordered levels, API limit 10 (2 recommended minimum)
    criteria: List[Content] = Field(max_length=10)


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion,
    Field(discriminator="type"),
]


class Request(BaseModel):
    state: Content
    model: str  # e.g. "jev-latest"
    # keys chosen by the caller; answers come back under the same keys
    questions: Dict[str, Question]


# ---------- Response ----------

class NoulAnswer(BaseModel):
    type: Literal[Type.NOUL]
    noul: float  # 0 (no) .. 1 (yes)
    confidence: float | None = None  # mentioned in the intro, absent from the schema


class ChoiceAnswer(BaseModel):
    type: Literal[Type.CHOICE]
    choice: str  # highest-probability option
    probabilities: Dict[str, float]  # option -> probability, sums to 1
    confidence: float  # 0..1


class ScoreAnswer(BaseModel):
    type: Literal[Type.SCORE]
    score: float  # probability-weighted, may fall between levels
    legend: Dict[str, str]  # level number (as string) -> description
    probabilities: Dict[str, float]  # level number (as string) -> probability
    confidence: float  # 0..1


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer,
    Field(discriminator="type"),
]


class Usage(BaseModel):
    # keep provider-specific fields (e.g. Laya's `truncated`, `state_tokens_dropped`)
    model_config = ConfigDict(extra="allow")

    input_tokens: int
    output_tokens: int


class Response(BaseModel):
    # keep provider-specific fields (e.g. Laya's `routing`)
    model_config = ConfigDict(extra="allow")

    model: str
    answers: Dict[str, Answer]
    usage: Usage

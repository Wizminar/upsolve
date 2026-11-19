"""Pydantic models that shape the public API (and its OpenAPI document)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SyncJob(BaseModel):
    id: int
    handle: str
    status: Literal["queued", "running", "done", "failed"]
    stage: str | None = Field(None, description="Current pipeline stage while running")
    started_at: int | None = None
    finished_at: int | None = None
    new_submissions: int = 0
    message: str | None = None


class Profile(BaseModel):
    handle: str
    rating: int | None = Field(None, description="Official Codeforces contest rating")
    max_rating: int | None = None
    rank: str | None = None
    max_rank: str | None = None
    avatar: str | None = None
    country: str | None = None
    practice_rating: int = Field(description="Upsolve's overall Elo practice rating")
    practice_rank: str | None = None
    submissions: int
    attempts: int = Field(description="Distinct problems attempted (submissions grouped per problem)")
    problems_solved: int
    solved_within_24h: int
    last_synced_at: int | None
    model_source: Literal["model", "elo"] = Field(description="'model' when the trained classifier is loaded, else Elo fallback")


class Topic(BaseModel):
    tag: str
    rating: int
    rank: str | None
    attempts: int
    solved: int
    solve_rate: float | None
    relative: int = Field(description="Topic rating minus overall practice rating")
    confidence: Literal["low", "medium", "high"] = Field(description="Evidence level: <5, <20, >=20 attempts")
    focus: bool
    hardest_solved: int | None = Field(None, description="Highest-rated problem with this tag the user has solved")


class HistoryPoint(BaseModel):
    at: int
    rating: int


class RatingChange(BaseModel):
    contest_id: int
    contest_name: str | None
    rank: int | None
    old_rating: int | None
    new_rating: int | None
    at: int | None


class ActivityDay(BaseModel):
    day: str
    submissions: int
    accepted: int


class Reason(BaseModel):
    kind: Literal["probability", "difficulty", "focus", "weak", "new", "upsolve"]
    text: str


class Recommendation(BaseModel):
    problem_id: str
    name: str
    rating: int
    rank: str | None
    tags: list[str]
    url: str
    solved_count: int
    probability: float = Field(description="Estimated solve probability (an estimate, not a promise)")
    reasons: list[Reason]
    upsolve: bool = Field(description="True when the user tried this problem before without solving it")


class Recommendations(BaseModel):
    handle: str
    practice_rating: int
    source: Literal["model", "elo"]
    target: list[float]
    stretch_zone: list[int] = Field(description="Problem ratings where the estimate is 50–70% for an unfamiliar topic")
    focus: list[str]
    items: list[Recommendation]


class Prediction(BaseModel):
    problem_id: str
    name: str
    rating: int
    tags: list[str]
    probability: float
    elo_probability: float
    source: Literal["model", "elo"]
    contributions: dict[str, float] = Field(description="Per-feature contribution to the log-odds")
    reasons: list[Reason]


class Feedback(BaseModel):
    shown: int
    attempted: int
    solved: int
    mean_predicted: float | None
    observed_rate: float | None


class TrainingSettings(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=2, examples=[["dp", "graphs"]])
    weekly_target: int = Field(5, ge=1, le=30)


class TrainingOut(TrainingSettings):
    updated_at: int | None = None


class Plan(BaseModel):
    handle: str
    week_start: str
    focus: list[str]
    weekly_target: int
    progress: int
    days: list[dict[str, Any]]


class PluginInfo(BaseModel):
    id: str
    name: str | None
    version: str | None
    description: str = ""
    author: str = ""
    slots: list[str] = []
    entry_url: str | None = None
    valid: bool
    errors: list[str] = []
    enabled: bool


class PluginToggle(BaseModel):
    enabled: bool


class StoreValue(BaseModel):
    value: Any = Field(description="Any JSON value (max 256 KB)", examples=[{"rival": "jiangly"}])


class StoreItem(BaseModel):
    key: str
    value: Any
    updated_at: int | None

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.pipeline.schemas import ExtractedRequirement, RequirementKind

DEFAULT_CASES_DIR = Path(__file__).resolve().parents[3] / "evals" / "cases"

Tag = Literal["direct", "paraphrase", "absent", "adjacent_trap", "tempting_quote", "years", "degree", "no_info"]


class GoldRequirement(BaseModel):
    text: str
    type: RequirementKind
    gold: Literal["met", "not_met"]
    tags: list[Tag] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)

    def as_requirement(self) -> ExtractedRequirement:
        return ExtractedRequirement(text=self.text, type=self.type, job_quote=self.text)


class Case(BaseModel):
    case_id: str
    title: str
    resume: str
    requirements: list[GoldRequirement]


def load_cases(cases_dir: Path = DEFAULT_CASES_DIR) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(cases_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for job in data["jobs"]:
            cases.append(
                Case(
                    case_id=job["case_id"], title=job["title"], resume=data["resume"], requirements=job["requirements"]
                )
            )
    return cases

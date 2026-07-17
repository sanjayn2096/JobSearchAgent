from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TweakKind(str, Enum):
    ADD = "add"
    REWORD = "reword"
    REMOVE = "remove"
    SURFACE = "surface"


@dataclass
class ResumeTweak:
    kind: TweakKind
    section: str
    original: str
    suggested: str
    reason: str


@dataclass
class ResumeSuggestion:
    job_id: str
    job_title: str
    company: str
    tweaks: list[ResumeTweak] = field(default_factory=list)

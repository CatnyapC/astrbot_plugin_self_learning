"""DTOs for unified term memory ingestion/query."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TermCandidate:
    """Normalized term candidate extracted from chat."""

    surface: str
    canonical_term: str
    confidence: float
    evidence_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class TermEntity:
    """Concept entity persisted in AIC-backed memory."""

    entity_id: str
    canonical_name: str
    aliases: list[str]
    status: str
    confidence: float


@dataclass(slots=True)
class TermKnowledge:
    """Knowledge claim linked to a concept entity."""

    claim_type: str
    claim_subtype: str
    text: str
    confidence_live: float
    citations: list[int] = field(default_factory=list)


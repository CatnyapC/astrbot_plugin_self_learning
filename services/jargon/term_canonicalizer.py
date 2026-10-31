"""Term canonicalization helpers for unified term memory."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping


_WRAP_CHARS_RE = re.compile(r"^[`'\"“”‘’\(\)\[\]\{\}<>《》「」【】]+|[`'\"“”‘’\(\)\[\]\{\}<>《》「」【】]+$")
_EDGE_NOISE_RE = re.compile(r"^[\s\.,，。!！\?？:：;；\-_~·]+|[\s\.,，。!！\?？:：;；\-_~·]+$")
_INNER_SPACES_RE = re.compile(r"\s+")

_COMMON_PREFIXES = (
    "这个",
    "那个",
    "所谓",
    "就是",
    "叫做",
    "叫",
)
_COMMON_SUFFIXES = (
    "啊",
    "呀",
    "吧",
    "呢",
    "哦",
    "嘛",
)


@dataclass(slots=True)
class CanonicalizeResult:
    surface: str
    canonical_term: str
    confidence: float
    normalization_reason: str


class TermCanonicalizer:
    """Normalize term surfaces into a stable canonical key."""

    def __init__(self, alias_map: Mapping[str, str] | None = None) -> None:
        self._alias_map = {
            str(k or "").strip().lower(): str(v or "").strip().lower()
            for k, v in dict(alias_map or {}).items()
            if str(k or "").strip() and str(v or "").strip()
        }

    def canonicalize(self, surface: str) -> CanonicalizeResult:
        raw = str(surface or "").strip()
        if not raw:
            return CanonicalizeResult(
                surface="",
                canonical_term="",
                confidence=0.0,
                normalization_reason="empty",
            )

        reasons: list[str] = []
        confidence = 1.0

        normalized = unicodedata.normalize("NFKC", raw)
        if normalized != raw:
            reasons.append("nfkc")
            confidence -= 0.03

        cleaned = _WRAP_CHARS_RE.sub("", normalized).strip()
        if cleaned != normalized:
            reasons.append("strip_wrap")
            confidence -= 0.03

        cleaned2 = _EDGE_NOISE_RE.sub("", cleaned).strip()
        if cleaned2 != cleaned:
            reasons.append("strip_edge_noise")
            confidence -= 0.03
        cleaned = cleaned2

        compact = _INNER_SPACES_RE.sub("", cleaned)
        if compact != cleaned:
            reasons.append("collapse_spaces")
            confidence -= 0.02
        cleaned = compact.lower()

        stem = cleaned
        for pfx in _COMMON_PREFIXES:
            if stem.startswith(pfx) and len(stem) - len(pfx) >= 2:
                stem = stem[len(pfx):]
                reasons.append(f"trim_prefix:{pfx}")
                confidence -= 0.05
                break

        for sfx in _COMMON_SUFFIXES:
            if stem.endswith(sfx) and len(stem) - len(sfx) >= 2:
                stem = stem[: -len(sfx)]
                reasons.append(f"trim_suffix:{sfx}")
                confidence -= 0.05
                break

        canonical = self._alias_map.get(stem, stem)
        if canonical != stem:
            reasons.append("alias_map")
            confidence -= 0.02

        if len(canonical) <= 1:
            confidence -= 0.25
            reasons.append("too_short")

        return CanonicalizeResult(
            surface=raw,
            canonical_term=canonical,
            confidence=max(0.2, min(1.0, round(confidence, 4))),
            normalization_reason="|".join(reasons) if reasons else "identity",
        )


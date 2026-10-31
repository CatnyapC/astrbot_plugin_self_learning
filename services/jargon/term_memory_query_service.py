"""AIC-backed term memory query + soft recall gate."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger

from .term_canonicalizer import TermCanonicalizer
from .term_memory_types import TermEntity, TermKnowledge

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")
_MAX_ALIAS_SCAN = 5000


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _norm(text: str) -> str:
    return str(text or "").strip().lower()


@dataclass(slots=True)
class TermQueryHit:
    surface: str
    entity: TermEntity
    definitions: list[TermKnowledge] = field(default_factory=list)
    relations: list[TermKnowledge] = field(default_factory=list)
    score: float = 0.0


class TermMemoryQueryService:
    """Query concept entity/knowledge from AIC storage for prompt injection."""

    def __init__(self, config: Any, canonicalizer: TermCanonicalizer | None = None) -> None:
        self._config = config
        self._canonicalizer = canonicalizer or TermCanonicalizer()
        self._db_path = str(getattr(config, "term_memory_aic_db_path", "") or "").strip()
        if not self._db_path:
            self._db_path = str(getattr(config, "_term_memory_aic_db_path", "") or "").strip()
        self._soft_recall_last_ts: dict[tuple[str, str], int] = {}
        self._alias_cache: dict[str, tuple[float, list[tuple[str, str, float]]]] = {}
        self._alias_cache_ttl = int(getattr(config, "term_alias_cache_ttl_sec", 90) or 90)

    def set_db_path(self, path: str) -> None:
        self._db_path = str(path or "").strip()

    def query_terms_for_message(
        self,
        *,
        group_id: str,
        text: str,
        limit: int = 3,
    ) -> list[TermQueryHit]:
        gid = str(group_id or "").strip()
        msg = str(text or "").strip()
        if not gid or not msg or not self._db_path:
            return []
        try:
            with self._connect() as conn:
                alias_rows = self._get_alias_rows(conn, gid)
                candidates = self._match_candidates(alias_rows, msg)
                if not candidates:
                    return []

                hits: list[TermQueryHit] = []
                for surface, entity_id, score in candidates[: max(1, int(limit) * 3)]:
                    entity = self._load_entity(conn, gid, entity_id)
                    if entity is None:
                        continue
                    knowledge = self._load_knowledge(conn, gid, entity_id)
                    if not knowledge:
                        continue
                    definitions = [k for k in knowledge if k.claim_type == "concept_definition"]
                    relations = [k for k in knowledge if k.claim_type == "concept_relation"]
                    if not definitions and relations:
                        # Keep relation-only entity only when definition absent.
                        definitions = relations[:1]
                    hit = TermQueryHit(
                        surface=surface,
                        entity=entity,
                        definitions=definitions[:3],
                        relations=relations[:3],
                        score=score,
                    )
                    hits.append(hit)

                # dedupe by entity
                out: list[TermQueryHit] = []
                seen: set[str] = set()
                for hit in sorted(hits, key=lambda x: x.score, reverse=True):
                    if hit.entity.entity_id in seen:
                        continue
                    seen.add(hit.entity.entity_id)
                    out.append(hit)
                    if len(out) >= max(1, int(limit)):
                        break
                return out
        except Exception as exc:
            logger.warning(f"[TermMemoryQuery] query failed: {exc}")
            return []

    def build_soft_recall_context(
        self,
        *,
        group_id: str,
        hits: list[TermQueryHit],
        cooldown_sec: int = 86400,
        max_items: int = 1,
    ) -> str:
        gid = str(group_id or "").strip()
        if not gid or not hits:
            return ""
        now = int(time.time())
        lines: list[str] = []
        for hit in hits:
            key = (gid, hit.entity.entity_id)
            last_ts = int(self._soft_recall_last_ts.get(key, 0) or 0)
            if now - last_ts < max(60, int(cooldown_sec or 86400)):
                continue
            if not hit.definitions:
                continue
            brief = self._shorten(hit.definitions[0].text, max_len=50)
            lines.append(
                f"- 可自然提起：你们之前把「{hit.surface}」当作「{hit.entity.canonical_name}」相关概念（{brief}）。"
            )
            self._soft_recall_last_ts[key] = now
            if len(lines) >= max(1, int(max_items)):
                break
        if not lines:
            return ""
        return "术语轻回忆提示:\n" + "\n".join(lines)

    def _match_candidates(
        self,
        alias_rows: list[tuple[str, str, float]],
        text: str,
    ) -> list[tuple[str, str, float]]:
        msg_norm = _norm(text)
        tokens = [t for t in _TOKEN_RE.findall(msg_norm) if len(t) >= 2]
        token_set = set(tokens)

        candidates: list[tuple[str, str, float]] = []
        for alias, entity_id, conf in alias_rows:
            a = _norm(alias)
            if len(a) < 2:
                continue
            score = 0.0
            if a in msg_norm:
                score += 0.62
            if a in token_set:
                score += 0.24
            for t in token_set:
                c = self._canonicalizer.canonicalize(t).canonical_term
                if c and c == a:
                    score += 0.18
                    break
            if score <= 0.0:
                continue
            score = _clamp(score + (float(conf or 0.0) * 0.2))
            candidates.append((alias, entity_id, score))
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates

    def _load_entity(
        self,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
    ) -> TermEntity | None:
        row = conn.execute(
            """
            SELECT canonical_name, status, confidence
            FROM entity_registry
            WHERE group_id=? AND entity_id=?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (group_id, entity_id),
        ).fetchone()
        if row is None:
            return None
        alias_rows = conn.execute(
            """
            SELECT alias
            FROM entity_aliases
            WHERE group_id=? AND entity_id=?
            ORDER BY confidence DESC, updated_at DESC
            LIMIT 10
            """,
            (group_id, entity_id),
        ).fetchall()
        aliases = [str(r["alias"] or "").strip() for r in alias_rows if str(r["alias"] or "").strip()]
        return TermEntity(
            entity_id=str(entity_id),
            canonical_name=str(row["canonical_name"] or "").strip(),
            aliases=aliases,
            status=str(row["status"] or "active").strip() or "active",
            confidence=float(row["confidence"] or 0.0),
        )

    def _load_knowledge(
        self,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
    ) -> list[TermKnowledge]:
        conf_min = float(getattr(self._config, "term_confidence_min", 0.6) or 0.6)
        rows = conn.execute(
            """
            SELECT archive_id, item_text, message_ts, evidence_confidence, target_certainty, meta_json
            FROM impression_evidence
            WHERE group_id=? AND user_id=? AND item_type='knowledge'
              AND COALESCE(consistency_tag, 'support')='support'
            ORDER BY message_ts DESC, id DESC
            LIMIT 80
            """,
            (group_id, entity_id),
        ).fetchall()

        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            item_text = str(row["item_text"] or "").strip()
            if not item_text:
                continue
            meta: dict[str, Any] = {}
            raw_meta = str(row["meta_json"] or "").strip()
            if raw_meta:
                try:
                    parsed = json.loads(raw_meta)
                    if isinstance(parsed, dict):
                        meta = parsed
                except Exception:
                    meta = {}
            claim_type = str(meta.get("claim_type", "knowledge") or "knowledge").strip().lower()
            claim_subtype = str(meta.get("claim_subtype", "general") or "general").strip().lower()
            conf_live = _clamp(float(row["evidence_confidence"] or 0.0) * float(row["target_certainty"] or 0.0))
            if conf_live < conf_min:
                continue
            key = (claim_type, item_text)
            bucket = merged.get(key)
            archive_id = int(row["archive_id"] or 0)
            if bucket is None:
                merged[key] = {
                    "claim_type": claim_type,
                    "claim_subtype": claim_subtype,
                    "text": item_text,
                    "confidence_live": conf_live,
                    "citations": [archive_id] if archive_id > 0 else [],
                }
            else:
                bucket["confidence_live"] = max(float(bucket["confidence_live"]), conf_live)
                if archive_id > 0 and archive_id not in bucket["citations"]:
                    bucket["citations"].append(archive_id)

        out = [
            TermKnowledge(
                claim_type=str(v["claim_type"]),
                claim_subtype=str(v["claim_subtype"]),
                text=str(v["text"]),
                confidence_live=float(v["confidence_live"]),
                citations=[int(x) for x in list(v["citations"])[:5] if int(x) > 0],
            )
            for v in merged.values()
        ]
        out.sort(
            key=lambda x: (
                1 if x.claim_type == "concept_definition" else 0,
                x.confidence_live,
            ),
            reverse=True,
        )
        return out

    def _get_alias_rows(
        self,
        conn: sqlite3.Connection,
        group_id: str,
    ) -> list[tuple[str, str, float]]:
        now = time.time()
        cache = self._alias_cache.get(group_id)
        if cache and now - cache[0] <= max(10, self._alias_cache_ttl):
            return cache[1]

        rows = conn.execute(
            """
            SELECT alias, entity_id, confidence
            FROM entity_aliases
            WHERE group_id=?
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
            """,
            (group_id, _MAX_ALIAS_SCAN),
        ).fetchall()
        alias_rows = [
            (
                str(r["alias"] or "").strip(),
                str(r["entity_id"] or "").strip(),
                float(r["confidence"] or 0.0),
            )
            for r in rows
            if str(r["alias"] or "").strip() and str(r["entity_id"] or "").strip()
        ]
        self._alias_cache[group_id] = (now, alias_rows)
        return alias_rows

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _shorten(self, text: str, max_len: int = 50) -> str:
        s = str(text or "").strip()
        if len(s) <= max_len:
            return s
        return s[: max(8, max_len - 1)] + "…"


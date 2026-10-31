"""AIC-backed term memory ingest + legacy jargon migration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from typing import Any, Optional

from astrbot.api import logger

from .term_canonicalizer import TermCanonicalizer
from .term_memory_types import TermEntity

_AIC_DB_ENV = "AIC_IMPRESSIONS_DB_PATH"
_SYNTHETIC_ARCHIVE_BASE = 900_000_000
_MAX_EVIDENCE = 3


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _entity_id(canonical: str) -> str:
    token = str(canonical or "").strip().lower()
    if not token:
        return ""
    return "ent:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


class TermMemoryIngestService:
    """Persist term entity/knowledge into AIC schema (single source of truth)."""

    def __init__(self, config: Any, canonicalizer: Optional[TermCanonicalizer] = None) -> None:
        self._config = config
        self._canonicalizer = canonicalizer or TermCanonicalizer()
        self._db_path = self._resolve_aic_db_path(config)
        self._enabled = bool(getattr(config, "enable_term_memory_bridge", True))

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._db_path)

    async def ingest_term_entity(
        self,
        *,
        group_id: str,
        term: str,
        evidence_messages: list[dict[str, Any]] | None = None,
        confidence: float = 0.75,
        source: str = "self_learning_term",
    ) -> Optional[TermEntity]:
        if not self.enabled:
            return None
        gid = str(group_id or "").strip()
        if not gid:
            return None
        normalized = self._canonicalizer.canonicalize(term)
        canonical = str(normalized.canonical_term or "").strip()
        if len(canonical) < 2:
            return None
        entity_id = _entity_id(canonical)
        if not entity_id:
            return None
        now = int(time.time())

        aliases = {
            canonical,
            str(term or "").strip(),
            str(normalized.surface or "").strip(),
        }
        aliases = {a for a in aliases if a}
        entity_conf = _clamp(confidence * normalized.confidence)
        meta_json = json.dumps(
            {
                "source": source,
                "normalization_reason": normalized.normalization_reason,
                "canonical_confidence": normalized.confidence,
            },
            ensure_ascii=False,
        )

        try:
            with self._connect() as conn:
                self._ensure_schema(conn)
                self._upsert_entity_registry(
                    conn=conn,
                    group_id=gid,
                    entity_id=entity_id,
                    canonical=canonical,
                    confidence=entity_conf,
                    now=now,
                    meta_json=meta_json,
                )
                self._upsert_entity_aliases(
                    conn=conn,
                    group_id=gid,
                    entity_id=entity_id,
                    aliases=aliases,
                    confidence=entity_conf,
                    now=now,
                )
                self._insert_entity_evidence(
                    conn=conn,
                    group_id=gid,
                    entity_id=entity_id,
                    canonical=canonical,
                    evidence_messages=evidence_messages or [],
                    confidence=entity_conf,
                    now=now,
                    source=source,
                )
                conn.commit()
            return TermEntity(
                entity_id=entity_id,
                canonical_name=canonical,
                aliases=sorted(aliases),
                status="active",
                confidence=entity_conf,
            )
        except Exception as exc:
            logger.error(f"[TermMemory] ingest_term_entity failed: {exc}", exc_info=True)
            return None

    async def ingest_term_evidence(
        self,
        *,
        group_id: str,
        term: str,
        meaning: str,
        evidence_messages: list[dict[str, Any]] | None = None,
        relation_surfaces: list[str] | None = None,
        confidence: float = 0.78,
        source: str = "self_learning_jargon",
    ) -> bool:
        if not self.enabled:
            return False
        entity = await self.ingest_term_entity(
            group_id=group_id,
            term=term,
            evidence_messages=evidence_messages,
            confidence=confidence,
            source=source,
        )
        if entity is None:
            return False

        text = _normalize_text(meaning)
        if not text:
            return True

        gid = str(group_id or "").strip()
        now = int(time.time())
        ev_msgs = list(evidence_messages or [])
        if not ev_msgs:
            ev_msgs = self._build_synthetic_evidence(
                term=term,
                message_text=text,
                now=now,
            )

        # concept_definition
        definition_text = f"{entity.canonical_name}：{text}"
        meta_definition = {
            "source": source,
            "term": term,
            "canonical_term": entity.canonical_name,
            "claim_type": "concept_definition",
            "claim_subtype": "definition.identity",
        }

        # concept_relation (surface -> canonical)
        relation_rows: list[tuple[str, dict[str, Any]]] = []
        for raw_surface in list(relation_surfaces or [term]):
            s = str(raw_surface or "").strip()
            if not s:
                continue
            if s.lower() == entity.canonical_name.lower():
                continue
            relation_rows.append(
                (
                    f"{s} 是 {entity.canonical_name} 的别称",
                    {
                        "source": source,
                        "term": s,
                        "canonical_term": entity.canonical_name,
                        "claim_type": "concept_relation",
                        "claim_subtype": "general",
                    },
                )
            )

        try:
            with self._connect() as conn:
                self._ensure_schema(conn)
                self._insert_knowledge_evidence(
                    conn=conn,
                    group_id=gid,
                    entity_id=entity.entity_id,
                    item_text=definition_text,
                    evidence_messages=ev_msgs,
                    confidence=confidence,
                    now=now,
                    meta_base=meta_definition,
                )
                for rel_text, rel_meta in relation_rows:
                    self._insert_knowledge_evidence(
                        conn=conn,
                        group_id=gid,
                        entity_id=entity.entity_id,
                        item_text=rel_text,
                        evidence_messages=ev_msgs,
                        confidence=max(0.6, confidence - 0.08),
                        now=now,
                        meta_base=rel_meta,
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"[TermMemory] ingest_term_evidence failed: {exc}", exc_info=True)
            return False

    async def migrate_legacy_jargon(
        self,
        db_manager: Any,
        *,
        max_per_group: int = 5000,
    ) -> dict[str, int]:
        """One-shot migration: self_learning jargon -> AIC entity/knowledge."""
        report = {
            "groups": 0,
            "rows_seen": 0,
            "rows_migrated": 0,
            "rows_skipped": 0,
            "rows_failed": 0,
        }
        if not self.enabled:
            return report
        if db_manager is None:
            return report

        try:
            groups = await db_manager.get_jargon_groups()
        except Exception as exc:
            logger.error(f"[TermMemory] migrate: get_jargon_groups failed: {exc}")
            return report

        for g in list(groups or []):
            gid = str((g or {}).get("chat_id", "") or "").strip()
            if not gid:
                continue
            report["groups"] += 1
            raw_messages = await self._safe_get_recent_raw_messages(
                db_manager,
                gid,
                limit=max(200, max_per_group),
            )
            message_index = self._build_message_index(raw_messages)

            offset = 0
            while True:
                batch = await db_manager.get_recent_jargon_list(
                    group_id=gid,
                    limit=min(500, max_per_group),
                    offset=offset,
                    only_confirmed=False,
                )
                if not batch:
                    break
                offset += len(batch)

                for row in batch:
                    report["rows_seen"] += 1
                    content = str((row or {}).get("content", "") or "").strip()
                    meaning = str((row or {}).get("meaning", "") or "").strip()
                    is_jargon = bool((row or {}).get("is_jargon", False))
                    if not content:
                        report["rows_skipped"] += 1
                        continue

                    raw_content = row.get("raw_content", "[]") if isinstance(row, dict) else "[]"
                    evidence_messages = self._resolve_legacy_evidence_messages(
                        raw_content=raw_content,
                        message_index=message_index,
                    )
                    if not evidence_messages:
                        ev = self._build_synthetic_evidence(
                            term=content,
                            message_text=meaning or content,
                            now=int((row or {}).get("updated_at", 0) or time.time()),
                            synthetic_id=_SYNTHETIC_ARCHIVE_BASE + int((row or {}).get("id", 0) or 0),
                        )
                        evidence_messages.extend(ev)

                    ok = await self.ingest_term_entity(
                        group_id=gid,
                        term=content,
                        evidence_messages=evidence_messages,
                        confidence=0.62 if is_jargon else 0.5,
                        source="legacy_jargon_migration",
                    )
                    if not ok:
                        report["rows_failed"] += 1
                        continue

                    if is_jargon and meaning:
                        migrated = await self.ingest_term_evidence(
                            group_id=gid,
                            term=content,
                            meaning=meaning,
                            evidence_messages=evidence_messages,
                            relation_surfaces=[content],
                            confidence=0.65,
                            source="legacy_jargon_migration",
                        )
                        if migrated:
                            report["rows_migrated"] += 1
                        else:
                            report["rows_failed"] += 1
                    else:
                        report["rows_skipped"] += 1
        return report

    async def _safe_get_recent_raw_messages(
        self,
        db_manager: Any,
        group_id: str,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            rows = await db_manager.get_recent_raw_messages(group_id, limit=limit)
            return [dict(x) for x in list(rows or []) if isinstance(x, dict)]
        except Exception:
            return []

    def _resolve_aic_db_path(self, config: Any) -> str:
        direct = str(getattr(config, "term_memory_aic_db_path", "") or "").strip()
        if direct:
            return os.path.abspath(os.path.expanduser(direct))
        env_path = str(os.getenv(_AIC_DB_ENV, "") or "").strip()
        if env_path:
            return os.path.abspath(os.path.expanduser(env_path))

        data_dir = str(getattr(config, "data_dir", "") or "").strip()
        if data_dir:
            resolved_data_dir = os.path.abspath(os.path.expanduser(data_dir))
            parent = os.path.dirname(resolved_data_dir)

            # Prefer AstrBot standard plugin_data layout when data_dir is outside plugin_data,
            # e.g. data_dir=/.../data/self_learning_data -> /.../data/plugin_data/...
            candidates = [
                os.path.join(
                    parent,
                    "plugin_data",
                    "astrbot_plugin_auto_impression_card",
                    "impressions.db",
                ),
                # Compatible with data_dir already under plugin_data:
                # /.../plugin_data/astrbot_plugin_self_learning -> /.../plugin_data/...
                os.path.join(
                    parent,
                    "astrbot_plugin_auto_impression_card",
                    "impressions.db",
                ),
            ]
            for guessed in candidates:
                if os.path.exists(guessed):
                    return guessed
            # Fallback to preferred standard layout even before first DB creation.
            return candidates[0]
        return ""

    def _connect(self) -> sqlite3.Connection:
        if not self._db_path:
            raise RuntimeError("aic_db_path_empty")
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS impression_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_text TEXT NOT NULL,
                archive_id INTEGER NOT NULL,
                speaker_id TEXT NOT NULL,
                message_text TEXT NOT NULL,
                message_ts INTEGER NOT NULL,
                evidence_confidence REAL,
                joke_likelihood REAL,
                source_type TEXT,
                consistency_tag TEXT,
                target_certainty REAL,
                meta_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_registry (
                group_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'other',
                status TEXT NOT NULL DEFAULT 'candidate',
                confidence REAL NOT NULL DEFAULT 0.0,
                support_count INTEGER NOT NULL DEFAULT 0,
                oppose_count INTEGER NOT NULL DEFAULT 0,
                first_seen_ts INTEGER NOT NULL DEFAULT 0,
                last_seen_ts INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                meta_json TEXT,
                PRIMARY KEY (group_id, entity_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_aliases (
                group_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (group_id, alias, entity_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'other',
                archive_id INTEGER NOT NULL,
                speaker_id TEXT NOT NULL,
                message_ts INTEGER NOT NULL,
                evidence_confidence REAL,
                target_certainty REAL,
                source_type TEXT,
                stance TEXT,
                meta_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )

    def _upsert_entity_registry(
        self,
        *,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
        canonical: str,
        confidence: float,
        now: int,
        meta_json: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO entity_registry (
                group_id, entity_id, canonical_name, entity_type, status, confidence,
                support_count, oppose_count, first_seen_ts, last_seen_ts, updated_at, meta_json
            )
            VALUES (?, ?, ?, 'concept', 'active', ?, 1, 0, ?, ?, ?, ?)
            ON CONFLICT(group_id, entity_id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                entity_type='concept',
                status='active',
                confidence=max(entity_registry.confidence, excluded.confidence),
                support_count=max(entity_registry.support_count, excluded.support_count),
                first_seen_ts=min(entity_registry.first_seen_ts, excluded.first_seen_ts),
                last_seen_ts=max(entity_registry.last_seen_ts, excluded.last_seen_ts),
                updated_at=excluded.updated_at,
                meta_json=excluded.meta_json
            """,
            (
                group_id,
                entity_id,
                canonical,
                _clamp(confidence),
                now,
                now,
                now,
                meta_json,
            ),
        )

    def _upsert_entity_aliases(
        self,
        *,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
        aliases: set[str],
        confidence: float,
        now: int,
    ) -> None:
        for alias in sorted(aliases):
            conn.execute(
                """
                INSERT INTO entity_aliases (group_id, alias, entity_id, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(group_id, alias, entity_id) DO UPDATE SET
                    confidence=max(entity_aliases.confidence, excluded.confidence),
                    updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    alias,
                    entity_id,
                    _clamp(confidence),
                    now,
                ),
            )

    def _insert_entity_evidence(
        self,
        *,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
        canonical: str,
        evidence_messages: list[dict[str, Any]],
        confidence: float,
        now: int,
        source: str,
    ) -> None:
        rows = sorted(
            list(evidence_messages or []),
            key=lambda x: (int(x.get("message_ts", 0) or 0), int(x.get("archive_id", 0) or 0)),
            reverse=True,
        )[:_MAX_EVIDENCE]
        for ev in rows:
            archive_id = int(ev.get("archive_id", 0) or 0)
            speaker_id = str(ev.get("speaker_id", "") or "")
            message_ts = int(ev.get("message_ts", now) or now)
            if archive_id <= 0 or not speaker_id:
                continue
            exists = conn.execute(
                """
                SELECT 1 FROM entity_evidence
                WHERE group_id=? AND entity_id=? AND archive_id=? AND speaker_id=?
                LIMIT 1
                """,
                (group_id, entity_id, archive_id, speaker_id),
            ).fetchone()
            if exists is not None:
                continue
            conn.execute(
                """
                INSERT INTO entity_evidence (
                    group_id, entity_id, canonical_name, entity_type,
                    archive_id, speaker_id, message_ts,
                    evidence_confidence, target_certainty, source_type, stance, meta_json, created_at
                )
                VALUES (?, ?, ?, 'concept', ?, ?, ?, ?, ?, 'other', 'support', ?, ?)
                """,
                (
                    group_id,
                    entity_id,
                    canonical,
                    archive_id,
                    speaker_id,
                    message_ts,
                    _clamp(confidence),
                    _clamp(confidence),
                    json.dumps({"source": source}, ensure_ascii=False),
                    now,
                ),
            )

    def _insert_knowledge_evidence(
        self,
        *,
        conn: sqlite3.Connection,
        group_id: str,
        entity_id: str,
        item_text: str,
        evidence_messages: list[dict[str, Any]],
        confidence: float,
        now: int,
        meta_base: dict[str, Any],
    ) -> None:
        rows = sorted(
            list(evidence_messages or []),
            key=lambda x: (int(x.get("message_ts", 0) or 0), int(x.get("archive_id", 0) or 0)),
            reverse=True,
        )[:_MAX_EVIDENCE]
        for ev in rows:
            archive_id = int(ev.get("archive_id", 0) or 0)
            speaker_id = str(ev.get("speaker_id", "") or "")
            message_ts = int(ev.get("message_ts", now) or now)
            message_text = str(ev.get("message_text", "") or "").strip()
            if archive_id <= 0 or not speaker_id:
                continue
            consistency_tag = str(ev.get("consistency_tag", "support") or "support").strip().lower()
            if consistency_tag not in {"support", "oppose"}:
                consistency_tag = "support"
            exists = conn.execute(
                """
                SELECT 1 FROM impression_evidence
                WHERE group_id=? AND user_id=? AND item_type='knowledge'
                  AND item_text=? AND archive_id=? AND speaker_id=?
                  AND COALESCE(consistency_tag, '')=?
                LIMIT 1
                """,
                (
                    group_id,
                    entity_id,
                    item_text,
                    archive_id,
                    speaker_id,
                    consistency_tag,
                ),
            ).fetchone()
            if exists is not None:
                continue

            meta_json = dict(meta_base)
            meta_json["citation_id"] = self._build_citation_id(
                group_id=group_id,
                entity_id=entity_id,
                item_text=item_text,
                archive_id=archive_id,
                speaker_id=speaker_id,
            )
            meta_json["polarity"] = consistency_tag

            conn.execute(
                """
                INSERT INTO impression_evidence (
                    group_id, user_id, item_type, item_text, archive_id, speaker_id,
                    message_text, message_ts, evidence_confidence, joke_likelihood,
                    source_type, consistency_tag, target_certainty, meta_json, created_at
                )
                VALUES (?, ?, 'knowledge', ?, ?, ?, ?, ?, ?, 0.0, 'other', ?, ?, ?, ?)
                """,
                (
                    group_id,
                    entity_id,
                    item_text,
                    archive_id,
                    speaker_id,
                    message_text,
                    message_ts,
                    _clamp(confidence),
                    consistency_tag,
                    _clamp(confidence),
                    json.dumps(meta_json, ensure_ascii=False),
                    now,
                ),
            )

    def _build_synthetic_evidence(
        self,
        *,
        term: str,
        message_text: str,
        now: int,
        synthetic_id: int = 0,
    ) -> list[dict[str, Any]]:
        archive_id = synthetic_id if synthetic_id > 0 else (_SYNTHETIC_ARCHIVE_BASE + int(now % 1000000))
        return [
            {
                "archive_id": int(archive_id),
                "speaker_id": "legacy_migration",
                "message_text": str(message_text or term or "").strip(),
                "message_ts": int(now),
                "consistency_tag": "support",
            }
        ]

    def _build_citation_id(
        self,
        *,
        group_id: str,
        entity_id: str,
        item_text: str,
        archive_id: int,
        speaker_id: str,
    ) -> str:
        raw = "|".join(
            [
                str(group_id or ""),
                str(entity_id or ""),
                str(item_text or ""),
                str(int(archive_id or 0)),
                str(speaker_id or ""),
            ]
        )
        return "cit:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_message_index(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        idx: dict[str, list[dict[str, Any]]] = {}
        for row in list(rows or []):
            text = _normalize_text(str((row or {}).get("message", "") or ""))
            if not text:
                continue
            idx.setdefault(text, []).append(row)
        for lst in idx.values():
            lst.sort(key=lambda x: int(x.get("timestamp", 0) or 0), reverse=True)
        return idx

    def _resolve_legacy_evidence_messages(
        self,
        *,
        raw_content: Any,
        message_index: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        contexts: list[str] = []
        try:
            parsed = raw_content
            if isinstance(raw_content, str):
                parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                contexts = [str(x or "").strip() for x in parsed if str(x or "").strip()]
            elif isinstance(parsed, str) and parsed.strip():
                contexts = [parsed.strip()]
        except Exception:
            if isinstance(raw_content, str) and raw_content.strip():
                contexts = [raw_content.strip()]

        out: list[dict[str, Any]] = []
        seen_archive: set[int] = set()
        for ctx in contexts:
            key = _normalize_text(ctx)
            rows = message_index.get(key, [])
            if not rows:
                continue
            row = rows[0]
            archive_id = int(row.get("id", 0) or 0)
            if archive_id <= 0 or archive_id in seen_archive:
                continue
            seen_archive.add(archive_id)
            out.append(
                {
                    "archive_id": archive_id,
                    "speaker_id": str(row.get("sender_id", "") or ""),
                    "message_text": str(row.get("message", "") or ""),
                    "message_ts": int(row.get("timestamp", 0) or 0),
                    "consistency_tag": "support",
                }
            )
            if len(out) >= _MAX_EVIDENCE:
                break
        return out

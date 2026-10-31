import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from astrbot_plugin_self_learning.services.jargon.term_canonicalizer import (
    TermCanonicalizer,
)
from astrbot_plugin_self_learning.services.jargon.term_memory_query_service import (
    TermMemoryQueryService,
)


def _init_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE entity_registry (
                group_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                confidence REAL NOT NULL DEFAULT 0.0,
                updated_at INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE entity_aliases (
                group_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                updated_at INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE impression_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_text TEXT NOT NULL,
                archive_id INTEGER NOT NULL,
                speaker_id TEXT NOT NULL,
                message_ts INTEGER NOT NULL,
                evidence_confidence REAL,
                target_certainty REAL,
                consistency_tag TEXT,
                meta_json TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_query_service_returns_definition_and_cooldown(tmp_path):
    db_path = tmp_path / "aic_test.db"
    _init_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO entity_registry (group_id, entity_id, canonical_name, status, confidence, updated_at)
            VALUES ('g1', 'ent:abc', '永远的神', 'active', 0.91, 100)
            """
        )
        conn.execute(
            """
            INSERT INTO entity_aliases (group_id, alias, entity_id, confidence, updated_at)
            VALUES ('g1', 'yyds', 'ent:abc', 0.9, 100),
                   ('g1', '永远的神', 'ent:abc', 0.95, 100)
            """
        )
        conn.execute(
            """
            INSERT INTO impression_evidence (
                group_id, user_id, item_type, item_text, archive_id, speaker_id,
                message_ts, evidence_confidence, target_certainty, consistency_tag, meta_json
            )
            VALUES (?, ?, 'knowledge', ?, 123, 'u1', 120, 0.9, 0.95, 'support', ?)
            """,
            (
                "g1",
                "ent:abc",
                "永远的神：表示非常厉害、非常认可",
                json.dumps(
                    {
                        "claim_type": "concept_definition",
                        "claim_subtype": "definition.identity",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO impression_evidence (
                group_id, user_id, item_type, item_text, archive_id, speaker_id,
                message_ts, evidence_confidence, target_certainty, consistency_tag, meta_json
            )
            VALUES (?, ?, 'knowledge', ?, 124, 'u1', 121, 0.8, 0.9, 'support', ?)
            """,
            (
                "g1",
                "ent:abc",
                "yyds 是 永远的神 的别称",
                json.dumps(
                    {
                        "claim_type": "concept_relation",
                        "claim_subtype": "general",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    cfg = SimpleNamespace(
        term_memory_aic_db_path=str(db_path),
        term_confidence_min=0.6,
        term_alias_cache_ttl_sec=60,
    )
    svc = TermMemoryQueryService(config=cfg, canonicalizer=TermCanonicalizer())

    hits = svc.query_terms_for_message(group_id="g1", text="这波真yyds", limit=3)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.entity.entity_id == "ent:abc"
    assert hit.entity.canonical_name == "永远的神"
    assert hit.definitions
    assert "非常厉害" in hit.definitions[0].text

    first_soft = svc.build_soft_recall_context(
        group_id="g1",
        hits=hits,
        cooldown_sec=3600,
        max_items=1,
    )
    second_soft = svc.build_soft_recall_context(
        group_id="g1",
        hits=hits,
        cooldown_sec=3600,
        max_items=1,
    )

    assert "术语轻回忆提示" in first_soft
    assert second_soft == ""

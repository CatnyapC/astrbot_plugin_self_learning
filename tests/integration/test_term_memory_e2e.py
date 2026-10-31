import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot_plugin_self_learning.services.jargon.jargon_miner import JargonMinerManager
from astrbot_plugin_self_learning.services.jargon.jargon_query import JargonQueryService
from astrbot_plugin_self_learning.services.jargon.term_canonicalizer import TermCanonicalizer
from astrbot_plugin_self_learning.services.jargon.term_memory_ingest_service import (
    TermMemoryIngestService,
)
from astrbot_plugin_self_learning.services.jargon.term_memory_query_service import (
    TermMemoryQueryService,
)
from astrbot_plugin_self_learning.services.learning.message_pipeline import MessagePipeline


class _FakeLLM:
    async def generate_response(self, prompt: str, temperature: float = 0.3) -> str:
        if "请比较这两个推断结果" in prompt:
            return '{"is_similar": false, "reason": "上下文语义更具体"}'
        if "请仅根据这个词条本身" in prompt:
            return '{"meaning": "永远的神"}'
        return (
            '{"meaning": "群里用 yyds 表示 永远的神，常用于夸赞某人很厉害", '
            '"no_info": false}'
        )


class _FakeCollector:
    async def get_statistics(self, group_id: str):
        return {"raw_messages": 20}


class _FakeFilter:
    def __init__(self, example_context: str):
        self._example_context = example_context

    def get_jargon_candidates(self, group_id: str, top_k: int = 20):
        return [
            {
                "term": "yyds",
                "score": 1.35,
                "frequency": 12,
                "context_examples": [self._example_context],
            }
        ]


class _BridgeDb:
    def __init__(self, config, messages):
        self.config = config
        self._messages = messages

    async def get_recent_raw_messages(self, group_id: str, limit: int = 30):
        return list(self._messages)[:limit]

    async def get_recent_jargon_list(self, *args, **kwargs):
        return []


class _LegacyDb:
    def __init__(self):
        self.config = SimpleNamespace(
            term_memory_inject_max_items=3,
            term_memory_soft_recall=True,
            term_memory_soft_recall_cooldown_sec=86400,
        )

    async def get_recent_jargon_list(self, chat_id: str, limit: int = 100, only_confirmed: bool = True):
        return [
            {
                "content": "yyds",
                "meaning": "永远的神",
            }
        ]


def _make_config(db_path: Path, enable_bridge: bool = True):
    return SimpleNamespace(
        enable_term_memory_bridge=enable_bridge,
        term_memory_aic_db_path=str(db_path),
        term_memory_migrate_on_startup=False,
        term_memory_soft_recall=True,
        term_memory_soft_recall_cooldown_sec=60,
        term_memory_inject_max_items=3,
        term_confidence_min=0.6,
        term_alias_cache_ttl_sec=30,
        term_alias_map={"yyds": "永远的神"},
        data_dir=str(db_path.parent),
        jargon_min_messages=10,
        jargon_min_interval=0,
        enable_realtime_learning=False,
        enable_goal_driven_chat=False,
    )


@pytest.mark.asyncio
async def test_message_trigger_to_term_memory_injection_e2e(tmp_path):
    db_path = tmp_path / "impressions.db"
    config = _make_config(db_path, enable_bridge=True)

    context_line = "u1: 这波操作真是yyds"
    recent_messages = [
        {
            "id": i + 1,
            "sender_id": "u1",
            "message": context_line,
            "timestamp": 1700000000 + i,
        }
        for i in range(12)
    ]

    bridge_db = _BridgeDb(config=config, messages=recent_messages)
    canonicalizer = TermCanonicalizer(alias_map=config.term_alias_map)
    ingest = TermMemoryIngestService(config=config, canonicalizer=canonicalizer)
    query = TermMemoryQueryService(config=config, canonicalizer=canonicalizer)
    query.set_db_path(ingest.db_path)

    miner_manager = JargonMinerManager(
        llm_adapter=_FakeLLM(),
        db_manager=bridge_db,
        config=config,
        term_memory_ingest_service=ingest,
    )
    pipeline = MessagePipeline(
        plugin_config=config,
        message_collector=_FakeCollector(),
        enhanced_interaction=None,
        jargon_miner_manager=miner_manager,
        jargon_statistical_filter=_FakeFilter(example_context=context_line),
        v2_integration=None,
        realtime_processor=None,
        group_orchestrator=None,
        conversation_goal_manager=None,
        affection_manager=None,
        db_manager=bridge_db,
    )

    for _ in range(4):
        await pipeline.mine_jargon("g1")
        await asyncio.sleep(0.05)

    jargon_query = JargonQueryService(
        db_manager=bridge_db,
        term_memory_query_service=query,
    )
    injected = await jargon_query.check_and_explain_jargon(
        text="我也觉得这把就是yyds",
        chat_id="g1",
    )

    assert injected is not None
    assert "术语记忆上下文" in injected
    assert "永远的神" in injected


@pytest.mark.asyncio
async def test_disable_term_bridge_fallbacks_to_legacy_jargon_query():
    legacy_db = _LegacyDb()
    jargon_query = JargonQueryService(db_manager=legacy_db, term_memory_query_service=None)

    explanation = await jargon_query.check_and_explain_jargon(
        text="这波就是yyds",
        chat_id="g1",
    )

    assert explanation is not None
    assert "文本中包含的黑话" in explanation
    assert "永远的神" in explanation

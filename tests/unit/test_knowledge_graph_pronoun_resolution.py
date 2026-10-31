from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_self_learning.core.interfaces import MessageData
from astrbot_plugin_self_learning.services.integration.knowledge_graph_manager import (
    KnowledgeGraphManager,
)


class _FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    async def generate_response(self, prompt: str, temperature: float = 0.1, model_type: str = "") -> str:
        self.prompts.append(
            {
                "prompt": prompt,
                "temperature": temperature,
                "model_type": model_type,
            }
        )
        return self._responses.pop(0)


def _fresh_manager(llm_adapter=None) -> KnowledgeGraphManager:
    KnowledgeGraphManager._instance = None
    KnowledgeGraphManager._initialized = False
    return KnowledgeGraphManager(config=None, db_manager=None, llm_adapter=llm_adapter)


@pytest.mark.asyncio
async def test_extract_relations_resolve_first_person_and_drop_unresolved_pronouns():
    llm = _FakeLLM(
        [
            '["我的袜子", "张三", "我", "他"]',
            '[["张三", "闻过", "我的袜子"], ["我", "拥有", "我的袜子"], ["他", "闻过", "你的袜子"]]',
        ]
    )
    manager = _fresh_manager(llm)

    entities = await manager.extract_entities_from_text(
        "反正闻过我的了",
        speaker_id="954976604",
        speaker_name="小明",
    )
    relations = await manager.extract_relations_from_text(
        "反正闻过我的了",
        entities,
        speaker_id="954976604",
        speaker_name="小明",
    )

    assert "954976604的袜子" in entities
    assert "954976604" in entities
    assert "我的袜子" not in entities
    assert "我" not in entities
    assert "他" not in entities

    assert ("张三", "闻过", "954976604的袜子") in relations
    assert ("954976604", "拥有", "954976604的袜子") in relations
    assert ("他", "闻过", "你的袜子") not in relations

    entity_prompt = llm.prompts[0]["prompt"]
    relation_prompt = llm.prompts[1]["prompt"]
    assert "当前消息说话人用户ID: 954976604" in entity_prompt
    assert "当前消息说话人用户ID: 954976604" in relation_prompt
    assert "必须解析成该用户ID" in entity_prompt
    assert "不要输出该三元组" in relation_prompt


@pytest.mark.asyncio
async def test_process_message_for_knowledge_graph_uses_speaker_aware_context_and_dedup_key():
    manager = _fresh_manager()
    manager._is_paragraph_processed = AsyncMock(return_value=False)
    manager._mark_paragraph_processed = AsyncMock()
    manager._update_entities = AsyncMock()
    manager._update_relations = AsyncMock()
    manager.extract_entities_from_text = AsyncMock(return_value=["954976604", "954976604的袜子", "123456"])
    manager.extract_relations_from_text = AsyncMock(
        return_value=[("123456", "闻过", "954976604的袜子")]
    )

    message = MessageData(
        sender_id="954976604",
        sender_name="小明",
        message="反正他闻过我的袜子了吧",
        group_id="971127073",
        timestamp=0.0,
        platform="qq",
    )

    await manager.process_message_for_knowledge_graph(message, "971127073")

    manager._is_paragraph_processed.assert_awaited_once_with(
        "954976604::反正他闻过我的袜子了吧",
        "971127073",
    )
    manager.extract_entities_from_text.assert_awaited_once_with(
        "反正他闻过我的袜子了吧",
        speaker_id="954976604",
        speaker_name="小明",
    )
    manager.extract_relations_from_text.assert_awaited_once_with(
        "反正他闻过我的袜子了吧",
        ["954976604", "954976604的袜子", "123456"],
        speaker_id="954976604",
        speaker_name="小明",
    )
    manager._mark_paragraph_processed.assert_awaited_once_with(
        "954976604::反正他闻过我的袜子了吧",
        "971127073",
    )

# Self Learning Term Memory Notes

## Scope
- This plugin now uses **Entity + Knowledge** for term memory (`concept entity` + `concept_definition/concept_relation`).
- `AIC` is the long-term source of truth.
- `self_learning` keeps low-cost trigger logic and online gating.

## Implemented Architecture

### 1) Trigger Layer (self_learning)
- `JargonStatisticalFilter` still discovers low-cost candidates per message.
- `MessagePipeline.mine_jargon(...)` now passes `recent_messages` into miner for evidence mapping.

### 2) Canonicalization Layer
- Added `TermCanonicalizer`:
  - NFKC normalization
  - wrapper/noise stripping
  - prefix/suffix trimming
  - alias mapping
- Output: `canonical_term`, `surface`, `confidence`, `normalization_reason`.

### 3) Entity Layer (AIC)
- Added `TermMemoryIngestService.ingest_term_entity(...)`.
- Candidate terms are persisted to AIC:
  - `entity_registry` (`entity_type=concept`)
  - `entity_aliases`
  - `entity_evidence` (with `archive_id/speaker_id/message_ts`)

### 4) Knowledge Layer (AIC)
- Added `TermMemoryIngestService.ingest_term_evidence(...)`.
- Confirmed/inferred term meaning writes:
  - `concept_definition`
  - `concept_relation` (surface alias relation)
- Stored in `impression_evidence` (`item_type='knowledge'`) with evidence and confidence gating.

### 5) Retrieval + Natural Mention
- Added `TermMemoryQueryService`:
  - `query_terms_for_message(...)`
  - `build_soft_recall_context(...)` (cooldown-based soft recall)
- `JargonQueryService` now prefers AIC term memory query and injects bounded context.
- If bridge/query service is disabled, falls back to legacy jargon query path.

## Bridge Mode Behavior (Important)
- In `JargonMiner`, when `enable_term_memory_bridge=true`:
  - legacy `jargon` table is **not** used as long-term store for new learning writes.
  - miner maintains in-memory short-term state for trigger/inference thresholds.
  - entity/knowledge goes to AIC.
- When bridge is off:
  - legacy jargon DB read/write behavior remains.

## Added Services / DTOs
- `services/jargon/term_canonicalizer.py`
- `services/jargon/term_memory_ingest_service.py`
- `services/jargon/term_memory_query_service.py`
- `services/jargon/term_memory_types.py`

## Config + Lifecycle Wiring
- Added `Term_Memory_Settings` in `_conf_schema.json`.
- Added config fields in `config.py`:
  - `enable_term_memory_bridge`
  - `term_memory_aic_db_path`
  - `term_memory_migrate_on_startup`
  - `term_memory_soft_recall`
  - `term_memory_soft_recall_cooldown_sec`
  - `term_memory_inject_max_items`
  - `term_confidence_min`
  - `term_alias_cache_ttl_sec`
  - `term_alias_map`
- `PluginLifecycle` now:
  - initializes canonicalizer/ingest/query services
  - injects term query service into `JargonQueryService`
  - injects term ingest service into `JargonMinerManager`
  - runs one-shot legacy migration on load when enabled

## Test Pipeline

### Unit tests
- `tests/unit/test_term_canonicalizer.py`
  - alias/noise normalization
  - empty input behavior
- `tests/unit/test_term_memory_query_service.py`
  - term hit -> definition retrieval
  - soft recall cooldown gate

### Integration tests
- `tests/integration/test_term_memory_e2e.py`
  - `message -> trigger -> entity+knowledge -> query inject` end-to-end path
  - bridge-off fallback to legacy jargon query

### Run commands
```bash
UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=/Users/lincoln/Git/AstrBot/data/plugins \
uv run pytest \
  tests/unit/test_term_canonicalizer.py \
  tests/unit/test_term_memory_query_service.py \
  tests/integration/test_term_memory_e2e.py -q
```

### Optional compile check
```bash
python3 -m py_compile \
  services/jargon/jargon_miner.py \
  services/jargon/jargon_query.py \
  services/jargon/term_canonicalizer.py \
  services/jargon/term_memory_ingest_service.py \
  services/jargon/term_memory_query_service.py \
  services/jargon/term_memory_types.py \
  services/learning/message_pipeline.py \
  core/plugin_lifecycle.py \
  config.py
```

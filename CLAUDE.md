# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Taiwanese-bank voice/STT-transcript PII masking pipeline (v3 + v4 tweaks), built on top of Microsoft Presidio. Input is Chinese (zh) text from call-center dialogues; output is masked text, an entities list, a conflict log, a value-to-token map, and usability tags. The rules are driven by `003_脫敏規則表_v3.docx` (the business spec), encoded in `config.py`.

v4 user-facing changes:
- `PseudonymTracker` no longer numbers tokens — every PERSON becomes `[NAME]` (not `[NAME_1]`/`[NAME_2]`), every TW_CREDIT_CARD becomes `[CARD]`, etc. The `pseudonym_map` still lists original values for audit.
- CKIP Transformers NER is **mandatory**: `MaskingPipeline.enable_ckip` has been removed, `get_all_custom_recognizers()` always registers `CkipNerRecognizer`. First `mask()` call lazy-loads the model; `ckip-transformers` + `torch` must be installed.
- CKIP now also emits `ORG` (機構名稱 → `[ORG]`); `ORG` is in `PSEUDONYM_ENTITIES` so originals appear in `pseudonym_map` for audit. Default `ckip_recognizer.py` `supported_entities` is `["PERSON", "LOCATION", "ORG"]`.
- **Step 4 LLM recognizer removed**. In production the downstream LLM consumes the already-masked `masked_text` after this pipeline finishes — it is no longer a Presidio recognizer inside the pipeline. `enable_llm_step`, `_build_llm_analyzer`, `_run_llm_step`, `_merge_results`, `AnonymizerEngine`, and `OperatorConfig` have all been deleted from `pipeline.py`. The former Step 4.5 `ConflictResolver` is now Step 4, making the flow a 6-step pipeline.

See `README.md` for installation and usage.

## Running

All scripts import modules at the repo root (flat layout — no `masking/` package). Run them from `/home/user/PII`.

- Demo with Presidio + blank zh spaCy model (no model download needed, NER off):
  ```
  python pipeline.py        # runs pipeline.demo()
  ```
- Interactive single-sentence / dialogue / Excel batch:
  ```
  python run_demo.py        # edit MODE = "single" | "dialogue" | "csv" at the top of the file
  ```
  Excel mode uses `openpyxl` and the column name defined by `CSV_COLUMN` (default `文本`); dialogue lines are parsed by `parse_dialogue_text()` in the format `坐席: <begin> <end> <text>` / `客戶: ...`.
- STT JSON batch (folder of `*.json` → `*_masked.json` + `stt_audit_log.csv`):
  ```
  python run_stt.py         # edit INPUT_PATH / OUTPUT_DIR at top of main()
  ```
  Role mapping depends on `DIALOGUE_INFO.DIRECTION`: inbound `I` → `R1=AGENT, R0=CUSTOMER`; outbound `O` → `R0=AGENT, R1=CUSTOMER`.

## Tests

There are currently no test files committed at the repo root (older `test_normalizer.py` / `test_pseudonym.py` were deleted — see `git log`). Add new tests at the repo root when introducing new behavior; run with plain `pytest`.

## Dependencies (implicit)

Install as needed — there is no lockfile:

```
pip install presidio-analyzer presidio-anonymizer spacy
pip install ckip-transformers torch      # mandatory: CKIP NER for PERSON/LOCATION
pip install openpyxl                     # optional: Excel batch inputs
```

`_build_analyzer()` in `pipeline.py:268` tries to load the configured spaCy model (default `zh_core_web_sm`); on failure it emits a `RuntimeWarning` and falls back to Presidio's default engine (Chinese NER then won't fire). Demos work around this by writing a `spacy.blank("zh")` model to a temp directory and passing `spacy_model=<that path>`.

## Pipeline architecture

`MaskingPipeline.mask()` in `pipeline.py` is the single entry point for one utterance. `mask_dialogue()` wraps it for a list of `DialogueTurn`s and shares one `PseudonymTracker` across turns. The 6-step flow is:

1. **Step 0 — Normalize** (`normalizer.normalize`): NFC → full-width→half-width → Chinese numerals→Arabic → ROC year→CE year → STT filler repeat collapse → whitespace. Order matters: numerals must run before ROC year so that "民國一一三年" → "民國113年" → "2024年".
2. **Step 1+2 — Presidio analyze**: `AnalyzerEngine` with custom recognizers from `recognizers.get_all_custom_recognizers()` (regex-based TW recognizers + mandatory CKIP NER for PERSON/LOCATION/ORG). Supported entity types are the keys of `TOKEN_MAP` in `config.py`. `BRANCH` is dropped from the request list unless `mask_branch_code=True`.
3. **Step 3 — Bank rules** (`_apply_bank_rules`):
   - `AMOUNT` is conditional: kept only if within `AMOUNT_PROXIMITY_CHARS` (60) of a `TW_BANK_ACCOUNT` / `TW_CREDIT_CARD`. Otherwise dropped. `AMOUNT_TXN` (from `AmountTxnRecognizer`, triggered by `HIGH_RISK_TXN_VERBS`) is always kept.
   - Speaker-aware: `_apply_speaker_aware_masking` does **not** filter by speaker — every speaker with PII gets masked. Diarization is used only as a fallback signal: when `diarization_available=False`, results inside the window after an `AGENT_QUESTION_PATTERNS` question or inside an `ANSWER_PATTERNS` match get a confidence boost.
4. **Step 4 — Conflict resolver** (`conflict_resolver.ConflictResolver`): resolves overlapping spans from different recognizers. Strategy (in order): (0) **Exact Duplicate Dedup** — `(start, end, entity_type)` identical triples are collapsed to the highest-scoring entry (ties keep first occurrence), handling CKIP × `AddressEnhancedRecognizer` duplicate detection of LOCATION (and any future overlap with spaCy NER if a non-blank spaCy model is ever configured); (1) longer-span wins if one strictly contains the other; (2) higher `ENTITY_RISK_LEVEL` wins on partial overlap; (3) longer span; (4) composite `_compute_priority_score` = `ENTITY_PRIORITY*0.4 + risk*10*0.4 + presidio_score*10*0.1 + keyword_bonus*0.1`. Returns `(clean_results, conflict_log)` where **entries are `(winner_result: RecognizerResult, loser_result: RecognizerResult, reason: str)`** — `pipeline.py` uses `id(winner)` to populate the audit log's `conflict_resolved` column.
5. **Step 5 — Token replacement** (`pseudonym.PseudonymTracker`): entity types in `PSEUDONYM_ENTITIES` get a flat base token (`[NAME]`, `[CARD]`, …) — v4 removed the session-stable `_1`/`_2` numbering. `pseudonym_map` still records `{entity_type: {original_value: base_token}}` for audit. Token replacement is done per-span by `_apply_per_span_replacement` (reverse-sorted by `start`) — Presidio's `anonymize()` is **not** used because its `operators` dict is keyed by `entity_type`.
6. **Step 6 — Audit + usability** (`audit.AuditLogger`, `_compute_usability`): writes one CSV row per entity, plus computes a `UsabilityTag`:
   - `LOW_AUDIO_QUALITY` if `asr_confidence < asr_confidence_threshold` (0.70)
   - `FALLBACK_MODE` if no diarization but fallback question/answer patterns fired; `NO_DIARIZATION` if no diarization and no fallback signal
   - `DEGRADED_MASKING` if entity density > `DEGRADED_MASKING_THRESHOLD` (3 per 100 chars)
   - Otherwise `USABLE`
   `mask_dialogue` declares `diarization_available=True` only when the labeled-speaker ratio ≥ `diarization_threshold` (default 0.8) — avoids misjudging partial diarization.

`MaskingResult` (dataclass in `pipeline.py:38`) carries the outputs: `masked_text`, `entities_found`, `token_map` (keyed by `id(RecognizerResult)` because multiple spans can share an entity type), `pseudonym_map`, `conflict_log`, `usability_tag`, `fallback_mode`.

## Config-driven behavior

Almost all tunables are in `config.py`:
- `TOKEN_MAP` — the authoritative list of supported entity types and their mask tokens. Adding a new entity type means (a) adding it here, (b) adding a recognizer in `recognizers.py`, (c) assigning an `ENTITY_PRIORITY` and `ENTITY_RISK_LEVEL`, (d) optionally adding to `PSEUDONYM_ENTITIES` if its original values should appear in `pseudonym_map` for audit, (e) adding `_TYPE_DESC` in `audit.py`.
- `AMOUNT_TRIGGER_ENTITIES` / `AMOUNT_PROXIMITY_CHARS` — what counts as "amount near account".
- `HIGH_RISK_TXN_VERBS` — drives `AmountTxnRecognizer`.
- `ADMIN_DISTRICTS` / `CHAIN_LANDMARKS` / `LANDMARK_SUFFIX_PATTERN` / `PROXIMITY_PATTERN` — the three-layer address detector in `AddressEnhancedRecognizer`.
- `AGENT_QUESTION_PATTERNS` / `ANSWER_PATTERNS` / `FALLBACK_ANSWER_WINDOW_CHARS` — diarization fallback scoring.
- `UsabilityTag` class + `DEGRADED_MASKING_THRESHOLD` — usability tagging.
- `AUDIT_FIELDNAMES` — CSV columns; must match the keys written by `AuditLogger.log_v3`.

## Known v3/v4 bug fixes referenced in source

When touching these areas, keep the fixes intact — they are called out in docstrings and comments and re-introducing them is a regression:
- `pipeline.py` Bug 1: don't switch back to Presidio `anonymize()` with `operators` keyed by entity type — use per-span replacement. (After v4 removed numbering, every PERSON maps to `[NAME]`, so the same-type-overwrite bug wouldn't visibly trigger today, but keep per-span replacement — it's the correct pattern and the right base for any future per-span logic.)
- `pipeline.py` Bug 2/3: `conflict_resolved` is looked up by `id(r)` against the set of winner ids extracted from `conflict_log` — not by entity type. Requires `conflict_log` to store `RecognizerResult` objects (fixed in v4).
- `pipeline.py` Bug 4: `_compute_usability` branches on `diarization_available` only; there is no `in_fallback` parameter.
- `normalizer.py` Issue 1/2: Chinese numerals must run **before** ROC year conversion; `_parse_zh_number` handles 十/百/千 composition; `_clean_stt_repeats` only collapses explicit fillers in `_STT_FILLER_CHARS`, never generic CJK.
- `pipeline.mask_dialogue` Issue 3: `diarization_available` uses a labeled-ratio threshold, not `any(...)`.
- `conflict_resolver.py` v4 Step 0: exact-span dedup removes CKIP × `AddressEnhancedRecognizer` duplicate LOCATION detections (and would also catch any future duplication if spaCy NER is re-enabled). Do not bypass it.

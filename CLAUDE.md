# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Taiwanese-bank STT transcript PII masking pipeline built on Microsoft Presidio with custom Chinese regex recognizers and CKIP Transformers NER. Business rules source of truth: `003_脫敏規則表_v3.docx`, codified in `config.py`.

## Running

```bash
# install (CKIP is required — not optional)
pip install presidio-analyzer presidio-anonymizer spacy ckip-transformers torch
python -m spacy download zh_core_web_sm   # optional

# built-in demo
python pipeline.py
```

There is no test suite, linter, or build step configured. Validation is by running `python pipeline.py` and inspecting `audit.csv`.

## Architecture — 7-step pipeline

Entry point is `MaskingPipeline.mask()` in `pipeline.py`; `mask_dialogue()` wraps it for `DialogueTurn` sequences and shares a `PseudonymTracker` across turns.

| Step | Purpose | Module |
|---|---|---|
| 0 | Normalize (NFC, fullwidth→half, Chinese numerals, ROC year, STT fillers) | `normalizer.normalize` |
| 1+2 | Presidio analysis: regex recognizers + spaCy NER + CKIP NER | `recognizers.get_all_custom_recognizers` + `ckip_recognizer` |
| 3 | Bank rules: conditional `AMOUNT`, speaker-aware score boost | `pipeline._apply_bank_rules` |
| 4 | Optional LLM supplementation | `pipeline._run_llm_step` |
| 4.5 | Conflict resolution (5-tier) | `conflict_resolver.ConflictResolver` |
| 5 | Per-span token replacement | `pseudonym.PseudonymTracker` |
| 6 | Audit CSV + usability tag | `audit.AuditLogger` |

ConflictResolver tiers: Exact Dup dedup → Contains → Risk Level → Span Length → weighted Priority Score (`priority*0.4 + risk*4 + score + keyword_bonus*0.1`).

## Key design invariants (do not regress)

The header of `pipeline.py` enumerates v3 bug fixes. Touching these areas requires preserving the fix:

- **`pipeline._apply_per_span_replacement`** — must use per-span `OperatorConfig` with Presidio's itemized path. Do NOT revert to entity-type-keyed `operator_config` — same-type multi-hits overwrite each other.
- **`pipeline._compute_usability`** — no `in_fallback` parameter; derive from `diarization_available` and question-branch detection directly.
- **`ConflictResolver.resolve` Step 0** — `(start, end, entity_type)` exact-dup dedup; `conflict_log` stores `RecognizerResult` objects (not type strings) because `pipeline.py` tracks `audit.conflict_resolved` via `id(winner)`.
- **`normalizer.normalize`** — Chinese numerals MUST run before ROC-year parsing. `_parse_zh_number` handles 十/百/千 place values. `_clean_stt_repeats` only compresses chars in `_STT_FILLER_CHARS`.
- **`mask_dialogue`** — `diarization_available` decided by labeled-speaker coverage ≥ threshold, not `any(...)`.

## v4 invariants

- **Fixed token masking**: `PseudonymTracker.resolve()` always returns the base token (`[NAME]`, `[CARD]`, …); no `_1`/`_2` suffixes. `pseudonym_map` still records original→token mapping for audit.
- **CKIP is mandatory**: no `enable_ckip` flag. `get_all_custom_recognizers` always registers `CkipNerRecognizer`. Missing `ckip-transformers` raises `ImportError` on first `mask()`.

## Adding a new entity type

Must modify in lockstep:
1. `config.py` — `TOKEN_MAP`, `ENTITY_PRIORITY`, `ENTITY_RISK_LEVEL`
2. `recognizers.py` — new recognizer class + register in `get_all_custom_recognizers`
3. `audit.py` — `_TYPE_DESC` Chinese description
4. Optional: add to `PSEUDONYM_ENTITIES` if raw values should appear in `pseudonym_map`

## Tunable knobs (`config.py`)

`AMOUNT_PROXIMITY_CHARS` (60), `HIGH_RISK_TXN_VERBS`, `FALLBACK_ANSWER_WINDOW_CHARS` (30), `DEGRADED_MASKING_THRESHOLD` (3.0 per 100 chars), `ENTITY_PRIORITY`, `ENTITY_RISK_LEVEL`, `ADMIN_DISTRICTS`, `CHAIN_LANDMARKS`.

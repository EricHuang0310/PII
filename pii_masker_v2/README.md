# pii_masker v2

Taiwanese-bank voice / STT transcript PII masking pipeline — **v2 rewrite**.

This package is a standalone rewrite of the v3/v4 pipeline that lives at the repo root
(`/Users/Liang/Documents/PII/pipeline.py` etc.). The root version is **untouched** and
remains the production-stable fallback; this directory is a clean-slate redesign that
runs alongside it.

## What's different from v3/v4

- **Hexagonal package layout** (`src/pii_masker/`) — no more flat files at repo root.
- **Frozen domain model** — `Span`, `Detection`, `MaskingResult`, `MaskingPolicy` are all
  `@dataclass(frozen=True, slots=True)`. No in-place score mutation anywhere.
- **Config is data** — business rules live in versioned `policy/defaults.yaml`, loaded
  into a frozen `MaskingPolicy` dataclass, validated at startup. `config.py` is gone.
- **7-step pipeline** — adds **Step 7 fail-closed leak scanner**: after masking, the
  output is re-scanned by all detectors; any non-token PII match raises `PIILeakError`.
- **Presidio is optional** — CKIP Transformers NER is used directly; Presidio is one of
  many pluggable detector adapters.
- **Batched CKIP inference** — `pipeline/batch.py` groups turns for a single NER call.
- **Stable span IDs** — `Detection.span_id` is a UUID, not `id(obj)`. Survives JSON
  round-trips; audit events can be joined on it.
- **Structured audit** — JSONL is the default sink; CSV remains available. Audit schema
  is derived from `AuditEvent` dataclass fields (no hand-synced `AUDIT_FIELDNAMES` list).
- **Rule versioning** — every `MaskingResult` carries `policy_version` + `pipeline_version`
  so audit logs can answer "which rule set produced this decision?"
- **Full test suite** — unit, integration, golden regression, hypothesis property,
  leak injection, and perf budget tests.
- **Thread-safe tracker** — `PseudonymTracker` has an internal `threading.Lock`.

## Install

```bash
cd pii_masker_v2
pip install -e ".[dev,ckip,observability]"
```

CKIP models download on first use. For excel inputs add `[excel]`; for the optional
Presidio adapter add `[presidio]`.

## Quick start

```python
from pii_masker import mask, mask_dialogue, DialogueTurn
from pii_masker.config.loader import load_policy

policy = load_policy()  # loads policy/defaults.yaml

result = mask(
    text="我叫王小明,卡號1234567890123456",
    session_id="S001",
    diarization_available=True,
    policy=policy,
)
print(result.masked_text)       # 我叫[NAME],卡號[CARD]
print(result.detections)        # frozen tuple[Detection, ...]
print(result.leak_scan_passed)  # True (Step 7 fail-closed)
print(result.policy_version)    # v4.1.0
```

## CLI

```bash
pii-masker mask-text "我叫王小明,卡號1234567890123456"
pii-masker mask-csv input.csv --column 文本 --output masked.csv
pii-masker mask-stt ./stt_json/ --output ./masked/
pii-masker verify audit.jsonl
```

## Test

```bash
pytest --cov=src/pii_masker --cov-fail-under=80
pytest tests/golden -v     # parity against root pipeline.py (read-only oracle)
pytest tests/leak -v       # injected-PII fail-closed check
pytest tests/property -v   # hypothesis-driven invariants
```

## Relation to the root v3/v4 code

This directory **never modifies** `../pipeline.py`, `../config.py`, or any other file
at the repo root. They remain byte-identical and fully runnable:

```bash
cd ..
python pipeline.py   # still the original v3/v4 demo
```

Migration is opt-in per call site. See `MIGRATION.md` for the import mapping.

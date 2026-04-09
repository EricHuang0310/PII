# Migrating from v3/v4 to pii_masker v2

This file maps the root v3/v4 API (`/Users/Liang/Documents/PII/pipeline.py`
and friends) to the v2 package under `pii_masker_v2/`. The root code is
**not** modified — this is a pure side-by-side rewrite. Callers migrate
opt-in by switching imports when they are ready.

## Installation

```bash
cd pii_masker_v2
pip install -e ".[dev,observability]"
# Optional: CKIP NER for PERSON/LOCATION/ORG
pip install -e ".[ckip]"
```

## Import mapping

| v3/v4 (root) | v2 (`pii_masker_v2/`) |
|---|---|
| `from pipeline import MaskingPipeline, DialogueTurn, MaskingResult` | `from pii_masker import MaskingResult, DialogueTurn, Speaker` + `from pii_masker.pipeline.masker import MaskingPipeline` |
| `from config import TOKEN_MAP, ENTITY_PRIORITY, ...` | `from pii_masker.config.loader import load_policy` → returns a frozen `MaskingPolicy` |
| `from normalizer import normalize` | `from pii_masker.normalize import normalize` |
| `from recognizers import get_all_custom_recognizers` | `from pii_masker.detect.registry import build_all_detectors` |
| `from conflict_resolver import ConflictResolver` | `from pii_masker.resolve.resolver import resolve` (pure function) |
| `from pseudonym import PseudonymTracker` | `from pii_masker.tokenize.tracker import PseudonymTracker` |
| `from audit import AuditLogger` | `from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink` (default) or `CsvAuditSink` |

## Behavioral differences

### Same

- 6 of the 7 pipeline steps (normalize → detect → rules → resolve →
  tokenize → audit) produce semantically equivalent output on regex-
  detectable PII. The golden regression corpus in
  `tests/golden/fixtures/bank_dialogue.json` pins 19 canonical cases.
- All v3/v4 "do-not-regress" bug fixes are preserved and tested by name:
  - Normalize order (Chinese numeral before ROC year)
  - STT filler scope (only filler chars, not generic CJK)
  - Per-span replacement (never Presidio `anonymize()`)
  - Exact-duplicate dedup at Step 4.0
  - Conflict log stores Detection objects (not entity-type strings)
  - `diarization_available` uses labeled-speaker ratio
  - Usability tagging branches on `diarization_available` only
- Flat base tokens (v4 behavior): `[NAME]`, `[CARD]`, no `_1/_2` numbering.
- CKIP NER for PERSON / LOCATION / ORG with the same label → entity
  mapping as root.

### New in v2

1. **Step 7 fail-closed leak scanner**. After masking, v2 re-runs detectors
   on `masked_text` and raises `PIILeakError` if any non-token PII slips
   through. Disable per-call with `mask(..., fail_on_leak=False)`.
2. **Stable span IDs**. `Detection.span_id` is a UUID. Audit events,
   conflict logs, and token maps all join on it. v3/v4 used
   `id(RecognizerResult)` which is ephemeral.
3. **Frozen domain model**. `Detection`, `Span`, `MaskingResult`,
   `MaskingPolicy` are all `@dataclass(frozen=True, slots=True)`. No
   in-place mutation anywhere in the pipeline.
4. **Policy as data**. All business rules are in `policy/defaults.yaml`.
   Override per environment by passing `policy=load_policy(Path(...))` to
   the pipeline constructor.
5. **Thread-safe PseudonymTracker**. Internal `threading.Lock`.
6. **Structured JSONL audit** with `policy_version` + `pipeline_version`
   on every row. CSV sink still available via `CsvAuditSink`.
7. **Batched CKIP inference** via `CkipNerAdapter.detect_batch()`.
8. **Explicit CKIP warmup** via `CkipNerAdapter.warmup()` — no surprise
   cold start on the first mask.
9. **Optional Luhn / TW-ID checksum validation** behind the
   `strict_validation` policy flag.
10. **Helper scripts** for common operations (`scripts/rebuild_golden.py`,
    `scripts/benchmark.py`).

### Breaking changes

- `MaskingResult.entities_found` → `MaskingResult.detections`. Type is
  `tuple[Detection, ...]` (immutable). v3/v4 returned
  `List[RecognizerResult]`.
- `MaskingResult.token_map` is now `Mapping[str, str]` keyed by
  `span_id` (UUID), not `Mapping[int, str]` keyed by `id()`.
- `MaskingResult.conflict_log` items are `ConflictEntry` dataclass
  instances, not raw tuples.
- `DialogueTurn.speaker` is a `Speaker` enum, not a raw string. Use
  `Speaker.AGENT` / `Speaker.CUSTOMER` / `Speaker.UNKNOWN`.
- `config.py` does not exist in v2. All tunables live in
  `policy/defaults.yaml` and are accessed via `MaskingPolicy`. If you
  have code that reads `config.ENTITY_PRIORITY` directly, switch to
  `policy.priority_of(entity_type)`.
- `MaskingPipeline.__init__` no longer takes `log_path`. Construct an
  audit sink explicitly and pass `audit_sink=`.

## Running both pipelines side-by-side

You can run the legacy root pipeline and v2 in the same Python process
without collision. The packages don't share any modules:

```python
# Legacy path — unchanged
import sys; sys.path.insert(0, "/Users/Liang/Documents/PII")
from pipeline import MaskingPipeline as LegacyPipeline

# v2 path
from pii_masker.pipeline.masker import MaskingPipeline as V2Pipeline
from pii_masker.config.loader import load_policy

legacy = LegacyPipeline(log_path="legacy.csv")
v2 = V2Pipeline(policy=load_policy(), include_ckip=True)
```

This is the recommended pattern during migration: run both on the same
input, diff the outputs, and only switch a given call site when parity
is confirmed for the cases that matter to you.

## Migration checklist

- [ ] `pip install -e pii_masker_v2[dev,ckip]`
- [ ] Replace `from pipeline import MaskingPipeline` with `from pii_masker.pipeline.masker import MaskingPipeline`
- [ ] Replace `log_path=` with explicit `audit_sink=JsonlAuditSink(...)`
- [ ] Replace `speaker="AGENT"` string literals with `Speaker.AGENT`
- [ ] Replace `result.entities_found` with `result.detections`
- [ ] Replace `result.token_map[id(r)]` with `result.tokens[det.span_id]`
- [ ] If you read `config.XXX` directly, switch to `policy.XXX` via
      the loaded `MaskingPolicy`
- [ ] Wrap the first mask call in `try/except PIILeakError` OR pass
      `fail_on_leak=False` while you verify v2 output matches expectations
- [ ] Once parity is confirmed, remove the `fail_on_leak=False` override

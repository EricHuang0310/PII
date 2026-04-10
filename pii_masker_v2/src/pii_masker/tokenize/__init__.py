"""Step 5 — token replacement.

`PseudonymTracker` assigns a stable token per (entity_type, original_value)
pair, thread-safe via an internal lock. `replacer.replace` applies tokens
to a text by doing reverse-sorted per-span replacement — the same technique
used by v3/v4 to avoid Presidio's `operators`-by-entity-type overwrite bug.
"""

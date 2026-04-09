"""Step 4 — conflict resolution.

Each layer is a pure function. `resolver.resolve` composes them. Order:

    Step 0:  exact-duplicate dedup      (dedup.py)
    Step 1:  strict containment         (contains.py, applied via resolver)
    Step 2:  risk level                 (risk.py)
    Step 3:  span length                (length.py)
    Step 4:  composite priority score   (priority.py)

Layers 1–4 run per overlapping-pair inside `resolver.resolve_overlapping`.
"""

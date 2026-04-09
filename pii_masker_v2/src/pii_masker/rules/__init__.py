"""Step 3 — policy-driven transforms over the raw detection list.

Every rule is a pure function: `(detections, text, policy, ...) -> new list`.
Rules MUST return new Detection objects — never mutate their input. This is
the v2 contract that closes the v3/v4 `r.score +=` mutation bug.
"""

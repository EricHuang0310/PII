"""Step 6 — structured audit events and sinks."""

from pii_masker.audit.event import AuditEvent
from pii_masker.audit.schema import AUDIT_FIELDNAMES, event_as_dict
from pii_masker.audit.sinks.base import AuditSink

__all__ = ["AuditEvent", "AUDIT_FIELDNAMES", "AuditSink", "event_as_dict"]

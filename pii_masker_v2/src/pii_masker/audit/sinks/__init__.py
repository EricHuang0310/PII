"""Audit sink implementations — JSONL (default), CSV, Null."""

from pii_masker.audit.sinks.base import AuditSink
from pii_masker.audit.sinks.csv_sink import CsvAuditSink
from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.audit.sinks.null_sink import NullAuditSink

__all__ = ["AuditSink", "CsvAuditSink", "JsonlAuditSink", "NullAuditSink"]

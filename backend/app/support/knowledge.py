"""Versioned annotations bound to retrieved authorized sources; never a parallel ACL."""

import hashlib
import json
from pathlib import Path

from app.support.exact import plain

KNOWLEDGE = json.loads(
    Path(__file__).with_name("institutional_knowledge.json").read_text(encoding="utf-8")
)


def bound_entries(chunks):
    for chunk in chunks:
        digest = hashlib.sha256(chunk["excerpt"].encode()).hexdigest()
        for entry in KNOWLEDGE["entries"]:
            if entry["source_version"] == chunk.get("version") and entry["source_sha256"] == digest:
                yield chunk, entry


def bound_rules(chunks):
    return [rule for _, entry in bound_entries(chunks) for rule in entry["rules"]]


def atomic_rules(chunks):
    """Annotations enrich existing chunks without changing embeddings or source identities."""
    result = []
    aliases = {c.get("id", str(i)): f"F{i + 1}" for i, c in enumerate(chunks)}
    for chunk, entry in bound_entries(chunks):
        for rule in entry["rules"]:
            result.append(
                {"text": plain(rule["documentary_text"]), "reference": aliases[chunk["id"]]}
            )
    return result

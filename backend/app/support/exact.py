"""Exact entities and citation-local contracts. No fuzzy correction of factual strings."""

import re
import unicodedata
from collections.abc import Callable
from urllib.parse import urlsplit

EMAIL = re.compile(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", re.UNICODE)
PHONE = re.compile(r"(?<!\d)(?:\+?55[ .-]?)?\(?\d{2}\)?[ .-]?\d{4,5}[- ]\d{4}(?!\d)")
URL = re.compile(r"https?://[^\s<>\])]+")


def plain(value):
    return " ".join(value.split())


def folded(value):
    return "".join(
        c for c in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(c)
    )


def phone_key(value):
    digits = re.sub(r"\D", "", value)
    return digits[2:] if len(digits) in {12, 13} and digits.startswith("55") else digits


def has_exact_fields(text):
    return bool(
        EMAIL.search(text) or PHONE.search(text) or URL.search(text) or re.search(r"\d", text)
    )


def validate_exact(answer, evidence):
    """Whole entities first; digit-bag membership cannot validate a phone or deadline."""
    entities: list[tuple[re.Pattern[str], Callable[[str], str], str]] = [
        (EMAIL, str, "email"),
        (PHONE, phone_key, "phone"),
        (URL, str, "URL"),
    ]
    for pattern, key, label in entities:
        allowed = {key(m.group().rstrip(".,;")) for m in pattern.finditer(evidence)}
        for match in pattern.finditer(answer):
            value = match.group().rstrip(".,;")
            if key(value) not in allowed:
                raise ValueError(f"Unsupported {label}")
            if label == "URL" and ("](" + value + ")") in answer:
                import json
                from pathlib import Path

                policy = json.loads(
                    Path(__file__).with_name("link_policy.json").read_text(encoding="utf-8")
                )
                target = urlsplit(value)
                if target.username or target.password or target.port not in {None, 443, 80}:
                    raise ValueError("Unsafe URL destination")
                if target.hostname not in policy["https_hosts"] or target.scheme != "https":
                    raise ValueError("URL domain is not authorized")
    # Compare complete dates, amounts and number+unit pairs, preserving qualifiers.
    patterns = [
        r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b",
        r"R\$\s*\d+(?:[.,]\d+)?",
        r"\b\d+(?:[.,]\d+)?\s*(?:dias?\s*(?:uteis|corridos)?|horas?|tarifas?|%)",
        r"\b(?:primeiro|segundo|terceiro|quarto|quinto|sexto|setimo|oitavo|nono|decimo)\s+dia\s*(?:util|corrido)?",
    ]
    for value_pattern in patterns:
        allowed = set(re.findall(value_pattern, folded(plain(evidence)), re.I))
        if any(
            value not in allowed for value in re.findall(value_pattern, folded(plain(answer)), re.I)
        ):
            raise ValueError("Unsupported number, exact value or unit")


def cited_pairs(answer, chunks):
    """A trailing citation binds the preceding assertion, never the entire paragraph."""
    available = {str(c["id"]): c for c in chunks}
    available.update({f"F{i + 1}": c for i, c in enumerate(chunks)})
    for paragraph in re.split(r"\n\s*\n", answer):
        cursor = 0
        for match in re.finditer(r"(?:\[fonte:[^\]]+\]\s*)+", paragraph):
            refs = re.findall(r"\[fonte:([^]]+)\]", match.group())
            if any(ref not in available for ref in refs):
                raise ValueError("Missing or invented reference")
            claim = paragraph[cursor : match.start()].strip()
            if claim:
                yield claim, [available[ref] for ref in dict.fromkeys(refs)]
            cursor = match.end()
        if re.sub(r"[\s.,;:!?*]", "", paragraph[cursor:]):
            raise ValueError("Uncited trailing claim")

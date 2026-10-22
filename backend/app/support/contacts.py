"""Contact resolution is backend-owned, scoped, versioned and exact."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from app.support.exact import PHONE, phone_key
from app.support.knowledge import bound_entries

PATH = Path(__file__).with_name("institutional_contacts.json")
DIRECTORY = json.loads(PATH.read_text(encoding="utf-8"))
CONTACTS = {c["id"]: c for c in DIRECTORY["contacts"]}


def whatsapp_url(digits):
    if not isinstance(digits, str) or not re.fullmatch(r"[1-9]\d{7,14}", digits):
        raise ValueError("Invalid international phone")
    return "https://wa.me/" + digits


def validate_destination(url, digits):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.netloc == "wa.me" and url == whatsapp_url(digits)


for _contact in CONTACTS.values():
    if re.sub(r"\D", "", _contact["phone"]) != _contact["phone_digits"]:
        raise ValueError("Inconsistent contact phone")


def resolve_contact(identifier, topic_id, scopes, settings, chunks=(), *, agent_id=None):
    contact = CONTACTS.get(identifier)
    from app.agents.policies import authorize_tool, owner

    requester = agent_id or owner(topic_id)
    if contact and requester:
        policy = authorize_tool(requester, "contacts")
        if contact.get("owner_domain") != policy.domain:
            return None
    else:
        return None
    if not contact or not contact.get("enabled", True) or topic_id not in contact["domains"]:
        return None
    if not set(contact["required_scopes"]) <= set(scopes):
        return None
    if settings.app_env != "development" and "local_review" in contact["required_scopes"]:
        return None
    if contact["validation_status"] != "validated" and settings.app_env != "development":
        return None
    provenance = {
        "kind": contact["source_kind"],
        "file": contact["source_file"],
        "section": contact["source_section"],
        "page": contact["source_page"],
        "version": contact["source_version"],
        "directory_version": DIRECTORY["version"],
        "directory_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
        "institutionally_approved": contact["validation_status"] == "validated",
    }
    if contact.get("email_provenance"):
        provenance["email_override"] = contact["email_provenance"]
    if contact["source_kind"] == "document":
        bindings = [(c, e) for c, e in bound_entries(chunks) if identifier in e["contact_ids"]]
        if not bindings:
            return None
        source, entry = bindings[0]
        phones = {phone_key(m.group()) for m in PHONE.finditer(source["excerpt"])}
        if phone_key(contact["phone"]) not in phones:
            return None
        provenance.update(
            source_id=source["id"], source_sha256=entry["source_sha256"], knowledge_id=entry["id"]
        )
    return {
        "contact_id": identifier,
        "team": contact["team"],
        "domain": topic_id,
        "phone": contact["phone"],
        "phone_digits": contact["phone_digits"],
        "channel": "whatsapp" if contact.get("whatsapp_enabled", False) else "phone",
        "whatsapp_enabled": contact.get("whatsapp_enabled", False),
        "whatsapp_validation_status": contact.get("whatsapp_validation_status"),
        "owner_domain": contact["owner_domain"],
        "phone_e164": "+" + contact["phone_digits"],
        "url": whatsapp_url(contact["phone_digits"])
        if contact.get("whatsapp_enabled", False)
        else None,
        "label": "WhatsApp do Educacional"
        if identifier == "education"
        else "WhatsApp da Frequência"
        if identifier == "rh_frequency"
        else "Contato do Atendimento",
        "email": contact["email"],
        "email_url": "mailto:" + contact["email"] if contact["email_link_enabled"] else None,
        "validation_status": contact["validation_status"],
        "availability_status": contact["availability_status"],
        "provenance": provenance,
    }


def contacts_for_sources(topic_id, scopes, settings, chunks, answer, *, agent_id=None):
    # Only attach an entity actually present in the validated, cited answer.
    present = {phone_key(m.group()) for m in PHONE.finditer(answer)}
    resolved = []
    for identifier in CONTACTS:
        contact = resolve_contact(identifier, topic_id, scopes, settings, chunks, agent_id=agent_id)
        if contact and phone_key(contact["phone"]) in present:
            resolved.append(contact)
    return resolved

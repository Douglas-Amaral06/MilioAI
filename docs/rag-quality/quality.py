"""Offline artifact validation and deterministic evaluation, Python stdlib only.

No application imports, model execution, database access, HTTP clients or remote
schema resolution. Lexical indicators explicitly do not assess semantic fidelity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARTIFACT_FILES = {
    "registry": "document_registry.json",
    "evidence_catalog": "evidence_catalog.json",
    "conflicts": "conflicts.json",
    "coverage": "card_coverage.json",
}
CSV_COLUMNS = [
    "document_id", "document_name", "domain", "source_path", "source_version",
    "document_hash", "document_date", "last_review_date", "responsible_department",
    "responsible_reviewer", "approval_status", "validity_status", "identified_issues",
    "next_action", "review_notes",
]
CATEGORIES = {
    "direct", "semantic_paraphrase", "informal", "continuation", "context_switch",
    "no_information", "ambiguity", "conflicting_information", "authorization",
}
SCHEMA_KEYWORDS = {"$ref", "$schema", "$id", "$defs", "title", "description", "type",
    "properties", "required", "additionalProperties", "items", "minItems", "uniqueItems",
    "minLength", "pattern", "minimum", "enum", "format"}


class QualityError(ValueError):
    """Invalid local artifact or export; safe to display without a traceback."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QualityError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Chave JSON duplicada: {key}")
        result[key] = value
    return result


def parse_json(text: str, label: str) -> Any:
    def reject_constant(value):
        raise QualityError(f"{label}: constante JSON não finita: {value}")
    try:
        return json.loads(text, object_pairs_hook=_unique_json, parse_constant=reject_constant)
    except json.JSONDecodeError as error:
        raise QualityError(f"{label}: JSON inválido na linha {error.lineno}") from error


def read_json(path: Path) -> Any:
    return parse_json(read_text(path), path.name)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise QualityError(f"{path.name}: arquivo deve usar UTF-8") from error


def schema_definition_check(spec: dict, schema: dict, at: str = "schema") -> None:
    require(isinstance(spec, dict), f"{at}: definição de schema inválida")
    require(not set(spec) - SCHEMA_KEYWORDS, f"{at}: keyword de schema não suportada")
    if "$ref" in spec:
        value = spec["$ref"]
        require(isinstance(value, str) and value.startswith("#/$defs/") and value.count("/") == 2 and value.split("/")[-1] in schema["$defs"], f"{at}: referência de schema inválida ou remota")
    if "format" in spec:
        require(spec["format"] in ["date", "date-time"], f"{at}: formato de schema não suportado")
    if "type" in spec:
        types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
        require(all(t in ["null", "string", "boolean", "integer", "object", "array"] for t in types), f"{at}: tipo de schema não suportado")
    if "pattern" in spec:
        try:
            re.compile(spec["pattern"])
        except (re.error, TypeError) as error:
            raise QualityError(f"{at}: regex de schema inválida") from error
    for group in ["$defs", "properties"]:
        if group in spec:
            require(isinstance(spec[group], dict), f"{at}.{group}: objeto esperado")
            for key, child in spec[group].items():
                schema_definition_check(child, schema, f"{at}.{key}")
    if "items" in spec:
        schema_definition_check(spec["items"], schema, f"{at}.items")


def schema_check(value: Any, spec: dict, schema: dict, at: str = "$", depth: int = 0) -> None:
    """The published schemas use only this documented, fail-closed subset."""
    require(depth < 60, f"{at}: profundidade de schema excedida")
    require(not set(spec) - SCHEMA_KEYWORDS, f"{at}: keyword de schema não suportada")
    if "$ref" in spec:
        ref = spec["$ref"]
        require(ref.startswith("#/$defs/") and ref.count("/") == 2, f"{at}: referência de schema deve ser local")
        name = ref.split("/")[-1]
        require(name in schema["$defs"], f"{at}: definição inexistente: {name}")
        return schema_check(value, schema["$defs"][name], schema, at, depth + 1)
    types = spec.get("type", [])
    if isinstance(types, str):
        types = [types]
    kinds = {"null": lambda v: v is None, "string": lambda v: isinstance(v, str),
             "boolean": lambda v: isinstance(v, bool), "integer": lambda v: type(v) is int,
             "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list)}
    require(all(t in kinds for t in types), f"{at}: tipo de schema não suportado")
    require(not types or any(kinds[t](value) for t in types), f"{at}: tipo inválido; esperado {types}")
    if "enum" in spec:
        require(any(type(value) is type(v) and value == v for v in spec["enum"]), f"{at}: estado/valor inválido")
    if value is None:
        return
    if isinstance(value, dict):
        props = spec.get("properties", {})
        require(set(spec.get("required", [])) <= set(value), f"{at}: campos obrigatórios ausentes: {set(spec.get('required', []))-set(value)}")
        if spec.get("additionalProperties") is False:
            require(set(value) <= set(props), f"{at}: campos desconhecidos: {set(value)-set(props)}")
        for key in value.keys() & props.keys():
            schema_check(value[key], props[key], schema, f"{at}.{key}", depth + 1)
    if isinstance(value, list):
        require(len(value) >= spec.get("minItems", 0), f"{at}: registros/itens insuficientes")
        if spec.get("uniqueItems"):
            encoded = [json.dumps(v, sort_keys=True, ensure_ascii=False) for v in value]
            require(len(encoded) == len(set(encoded)), f"{at}: itens duplicados")
        for i, item in enumerate(value):
            schema_check(item, spec.get("items", {}), schema, f"{at}[{i}]", depth + 1)
    if isinstance(value, str):
        require(len(value) >= spec.get("minLength", 0), f"{at}: texto vazio")
        if "pattern" in spec:
            require(re.search(spec["pattern"], value) is not None, f"{at}: formato inválido")
        try:
            if spec.get("format") == "date":
                require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None, f"{at}: data inválida")
                date.fromisoformat(value)
            elif spec.get("format") == "date-time":
                require("T" in value, f"{at}: data/hora inválida")
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                require(parsed.tzinfo is not None, f"{at}: data/hora exige fuso")
            elif "format" in spec:
                raise QualityError(f"{at}: formato de schema não suportado")
        except ValueError as error:
            raise QualityError(f"{at}: data/hora inválida") from error
    if type(value) is int:
        require(value >= spec.get("minimum", value), f"{at}: página/valor abaixo do mínimo")


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    ids = [row[key] for row in rows]
    require(len(ids) == len(set(ids)), f"IDs duplicados: {key}")
    return dict(zip(ids, rows))


def safe_path(root: Path, value: str) -> Path:
    require(not PureWindowsPath(value).is_absolute() and not Path(value).is_absolute()
            and "\\" not in value and ":" not in value and ".." not in Path(value).parts,
            f"Caminho deve ser relativo e local: {value}")
    target = (root / value).resolve()
    require(target.is_relative_to(root.resolve()), f"Caminho fora do workspace: {value}")
    return target


def reference(evidence: dict) -> dict:
    return {key: evidence[key] for key in ["document_id", "source_version", "section_or_row", "page", "benefit_code"]}


def section_key(value: str | None) -> str | None:
    if value is None:
        return None
    numbered = re.match(r"^\s*(\d+\.)", value)
    return numbered.group(1) if numbered else value.strip().casefold()


def reference_matches(actual: dict, expected: dict) -> bool:
    if any(actual.get(k) != expected.get(k) for k in ["document_id", "source_version", "page", "benefit_code"]):
        return False
    if expected.get("benefit_code") is not None:
        # The exact benefit code is the row identifier. A document hit is not a card hit.
        section = actual.get("section_or_row")
        code = re.match(r"^\s*(\d+)(?:\s*[·.:-]|$)", section) if section is not None else None
        return section is None or (code is not None and code.group(1) == expected["benefit_code"])
    return section_key(actual.get("section_or_row")) == section_key(expected.get("section_or_row"))


def load_bundle(folder: Path = HERE) -> dict:
    schema = read_json(folder / "evaluation_schema.json")
    # Resolve every local definition even when not used by the current dataset.
    require(isinstance(schema.get("$defs"), dict), "Schema sem definições")
    schema_definition_check(schema, schema)
    data = {key: read_json(folder / name) for key, name in ARTIFACT_FILES.items()}
    for key, value in data.items():
        schema_check(value, schema["$defs"][key], schema, key)
    cases = []
    for number, line in enumerate(read_text(folder / "rag_eval_dataset.jsonl").splitlines(), 1):
        require(bool(line.strip()), f"Dataset: linha vazia {number}")
        value = parse_json(line, f"dataset:{number}")
        schema_check(value, schema["$defs"]["case"], schema, f"case:{number}")
        cases.append(value)
    data.update(cases=cases, schema=schema, folder=folder)
    return data


def csv_view(bundle: dict) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for doc in bundle["registry"]["documents"]:
        writer.writerow({key: " | ".join(doc[key]) if isinstance(doc[key], list) else doc[key] if doc[key] is not None else "" for key in CSV_COLUMNS})
    return stream.getvalue()


def conflicts_view(bundle: dict) -> str:
    evidence = index_by(bundle["evidence_catalog"]["evidence"], "evidence_id")
    lines = ["# Pendências e conflitos documentais", "", "Visão derivada de `conflicts.json`; nenhuma interpretação foi aprovada automaticamente.", ""]
    for conflict in bundle["conflicts"]["conflicts"]:
        lines += [f"## {conflict['conflict_id']} — {conflict['title']}", "",
                  f"Tipo: `{conflict['kind']}` · Gravidade: `{conflict['severity']}` · Estado: `{conflict['status']}`", ""]
        for eid in conflict["evidence_ids"]:
            item = evidence[eid]
            lines.append(f"- Fonte `{item['document_id']}`, versão `{item['source_version']}`, página {item['page'] if item['page'] is not None else 'não paginada'}, seção/registro `{item['section_or_row']}` (`{eid}`).")
        lines += ["", *[f"- {observation}" for observation in conflict["observations"]], "", f"Próxima ação: {conflict['next_action']}", "", "Revisor/data institucional: não informados." if conflict["responsible_reviewer"] is None else f"Revisor: {conflict['responsible_reviewer']}; data: {conflict['review_date']}", ""]
    return "\n".join(lines)


def validate_bundle(bundle: dict, root: Path = ROOT, check_views: bool = True) -> dict:
    schema = bundle["schema"]
    for key in ARTIFACT_FILES:
        schema_check(bundle[key], schema["$defs"][key], schema, key)
    for case in bundle["cases"]:
        schema_check(case, schema["$defs"]["case"], schema, case.get("test_id", "case"))
    docs = index_by(bundle["registry"]["documents"], "document_id")
    ev = index_by(bundle["evidence_catalog"]["evidence"], "evidence_id")
    cases = index_by(bundle["cases"], "test_id")
    conflicts = index_by(bundle["conflicts"]["conflicts"], "conflict_id")
    cards = index_by(bundle["coverage"]["cards"], "benefit_code")
    warnings = []
    version = bundle["registry"]["registry_version"]
    require(all(bundle[key]["version"] == version for key in ["evidence_catalog", "conflicts", "coverage"]), "Versões dos artefatos não coincidem")
    for doc in docs.values():
        require(set(doc["identified_issues"]) <= conflicts.keys(), f"{doc['document_id']}: conflito inexistente")
        if doc["source_availability"] == "original_missing":
            require(doc["source_path"] is None and doc["document_hash"] is None, f"{doc['document_id']}: hash/caminho do original ausente não pode ser inventado")
            require(doc["approval_status"] != "approved", f"{doc['document_id']}: original ausente não pode ser aprovado")
            warnings.append(f"{doc['document_id']}: PDF original ausente; evidência derivada, sem hash do original.")
        else:
            require(doc["source_path"] is not None and doc["document_hash"] is not None, f"{doc['document_id']}: fonte disponível exige caminho e hash")
            path = safe_path(root, doc["source_path"])
            require(path.is_file() and sha256(path) == doc["document_hash"], f"{doc['document_id']}: fonte alterada/ausente; revisar versão e hash")
        if doc["approval_status"] == "approved":
            require(doc["responsible_reviewer"] is not None and doc["last_review_date"] is not None
                    and doc["validity_status"] == "verified", f"{doc['document_id']}: aprovação exige revisor, data e vigência verificada")
            require(not any(c["severity"] in ["high", "critical"] and c["status"] not in ["resolved", "rejected"] for c in conflicts.values() if c["conflict_id"] in doc["identified_issues"]), f"{doc['document_id']}: aprovação com pendência grave aberta")
        for artifact in doc["artifacts"]:
            path = safe_path(root, artifact["path"])
            if path.is_file():
                require(sha256(path) == artifact["sha256"], f"{doc['document_id']}: artefato mudou: {artifact['path']}")
            else:
                warnings.append(f"Artefato auxiliar ausente neste checkout: {artifact['path']}")
    for item in ev.values():
        require(item["document_id"] in docs, f"{item['evidence_id']}: documento inexistente")
        doc = docs[item["document_id"]]
        require(item["source_version"] == doc["source_version"], f"{item['evidence_id']}: versão documental divergente")
        require((item["page"] is None and doc["page_count"] is None) or (type(item["page"]) is int and doc["page_count"] is not None and item["page"] <= doc["page_count"]), f"{item['evidence_id']}: página inválida")
        require(hashlib.sha256(item["excerpt"].encode()).hexdigest() == item["excerpt_sha256"], f"{item['evidence_id']}: hash do trecho divergente")
        if item["benefit_code"] is not None:
            require(item["benefit_code"] in cards, f"{item['evidence_id']}: código de cartão inexistente")
    for conflict in conflicts.values():
        require(set(conflict["evidence_ids"]) <= ev.keys(), f"{conflict['conflict_id']}: evidência inexistente")
        if conflict["status"] == "resolved":
            require(all(conflict[k] is not None for k in ["responsible_reviewer", "review_date", "resolution_notes"]), f"{conflict['conflict_id']}: resolução exige registro institucional")
    criteria_ids = []
    for case in cases.values():
        tid = case["test_id"]
        require(case["dataset_version"] == version, f"{tid}: versão do dataset divergente")
        require(set(case["relevant_evidence_ids"]) <= ev.keys(), f"{tid}: evidência inexistente")
        require(set(case["conflict_ids"]) <= conflicts.keys(), f"{tid}: conflito inexistente")
        require(set(case["run_context"]["allowed_document_ids"]) <= docs.keys(), f"{tid}: documento de contexto inexistente")
        relevant = [ev[eid] for eid in case["relevant_evidence_ids"]]
        first = relevant[0] if relevant else None
        for case_key, evidence_key in [("expected_document_id", "document_id"), ("expected_section_or_row", "section_or_row"), ("expected_page", "page")]:
            require(case[case_key] == (first[evidence_key] if first else None), f"{tid}: referência principal/página divergente das evidências")
        expected_refs = []
        for item in relevant:
            value = reference(item)
            if value not in expected_refs:
                expected_refs.append(value)
            require(item["document_id"] in case["run_context"]["allowed_document_ids"], f"{tid}: fonte esperada fora do contexto permitido")
        require(case["expected_citation"] == expected_refs, f"{tid}: citação sem evidência ou referência divergente")
        require(case["requires_context"] == bool(case["conversation_context"]["prior_turns"]), f"{tid}: contexto incompleto")
        if case["question_type"] in ["continuation", "context_switch"]:
            require(case["requires_context"], f"{tid}: categoria exige histórico")
        if case["question_type"] == "conflicting_information":
            require(case["conflict_ids"] and case["expected_behavior"] == "surface_conflict", f"{tid}: conflito exige referência e explicitação")
        for code in [case["expected_context"]["benefit_code"], case["conversation_context"]["selected_benefit_code"]]:
            require(code is None or code in cards, f"{tid}: código contextual inexistente")
        for criterion in case["expected_facts"] + case["forbidden_claims"]:
            criteria_ids.append(criterion["criterion_id"])
            require(set(criterion["evidence_ids"]) <= set(case["relevant_evidence_ids"]), f"{tid}: critério sem evidência referenciada no caso")
            require(all(normalize(alias) for group in criterion["match"]["all_of"] for alias in group), f"{tid}: alias de critério vazio após normalização")
        if case["expected_behavior"] in ["answer", "surface_conflict"]:
            require(bool(relevant) and all(c["evidence_ids"] for c in case["expected_facts"]), f"{tid}: fatos de resposta exigem evidência documental")
    require(len(criteria_ids) == len(set(criteria_ids)), "IDs de critérios duplicados")
    source_codes = bundle["coverage"]["source_card_codes"]
    require(bundle["coverage"]["expected_card_count"] == 33 and len(cards) == 33
            and set(cards) == set(source_codes), "Cobertura deve rastrear exatamente os 33 códigos da fonte")
    for card in cards.values():
        require(card["evidence_id"] in ev and card["document_id"] in docs, f"{card['benefit_code']}: referência inexistente")
        item = ev[card["evidence_id"]]
        require(all(item[k] == card[k] for k in ["benefit_code", "document_id", "page"]), f"{card['benefit_code']}: página/código documental divergente")
        require(card["extraction_status"] == "snapshot_verified", f"{card['benefit_code']}: extração pendente; cobertura documental incompleta")
        fields = item["observed_fields"]
        require(all(isinstance(fields.get(k), str) and fields[k].strip() for k in ["name", "requester", "payer", "payment", "fee"]), f"{card['benefit_code']}: registro de cartão incompleto")
        require(fields["name"] == card["name"] and docs[card["document_id"]]["domain"] == "vale_transporte", f"{card['benefit_code']}: identidade/domínio do cartão divergente")
        require(set(card["test_ids"]) <= cases.keys(), f"{card['benefit_code']}: caso inexistente")
        actual = {c["test_id"] for c in cases.values() if c["domain"] == "vale_transporte" and c["expected_context"]["benefit_code"] == card["benefit_code"]}
        require(set(card["test_ids"]) == actual and actual, f"{card['benefit_code']}: cobertura de casos desatualizada")
        require(set(card["issue_ids"]) <= conflicts.keys(), f"{card['benefit_code']}: pendência inexistente")
    for page in {c["page"] for c in cards.values()}:
        ordinals = [c["row_on_page"] for c in cards.values() if c["page"] == page]
        require(sorted(ordinals) == list(range(1, len(ordinals)+1)), f"Página {page}: ordem de linhas inconsistente")
    categories = Counter(c["question_type"] for c in cases.values())
    domains = Counter(c["domain"] for c in cases.values())
    require(CATEGORIES <= categories.keys(), "Categorias sem cobertura")
    require(domains["folha_ponto"] >= 12, "Pelo menos 12 casos de Folha Ponto são necessários")
    vt_codes = {c["expected_context"]["benefit_code"] for c in cases.values() if c["domain"] == "vale_transporte" and c["expected_context"]["benefit_code"] is not None}
    require(len(vt_codes) >= 12, "Pelo menos 12 cartões distintos precisam de casos")
    require(categories["continuation"] >= 6, "Pelo menos 6 casos de continuidade são necessários")
    require(categories["no_information"] + categories["ambiguity"] >= 6, "Pelo menos 6 casos negativos/ambíguos são necessários")
    if check_views:
        for name, value in [("validation_registry.csv", csv_view(bundle)), ("conflicts.md", conflicts_view(bundle))]:
            path = bundle["folder"] / name
            require(path.is_file() and path.read_text(encoding="utf-8-sig") == value, f"{name}: visão desatualizada; execute render-views")
    return {"status": "valid", "dataset_version": version, "cases": len(cases), "domains": dict(sorted(domains.items())),
            "categories": dict(sorted(categories.items())), "document_records": len(docs), "evidence_records": len(ev),
            "card_coverage": {"expected": 33, "covered": len(vt_codes), "pages": dict(sorted(Counter(c["page"] for c in cards.values()).items()))},
            "conflicts": len(conflicts), "approved_documents": sum(d["approval_status"] == "approved" for d in docs.values()),
            "warnings": sorted(set(warnings)), "model_execution": "not_performed", "rag_performance": "not_measured"}


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def lexical_match(answer: str, criterion: dict) -> bool:
    text = " " + normalize(answer) + " "
    return all(any(" " + normalize(alias) + " " in text for alias in group) for group in criterion["match"]["all_of"])


def source_allowed(ref: dict, case: dict, docs: dict, conflicts: dict) -> tuple[bool, str]:
    doc = docs.get(ref["document_id"])
    if doc is None:
        return False, "unknown_document"
    if ref["source_version"] != doc["source_version"]:
        return False, "unregistered_version"
    if ref.get("document_hash") is not None and doc["document_hash"] is not None and ref["document_hash"] != doc["document_hash"]:
        return False, "source_hash_mismatch"
    context = case["run_context"]
    if doc["document_id"] not in context["allowed_document_ids"]:
        return False, "outside_case_scope"
    if not set(doc["required_scopes"]) <= set(context["scopes"]):
        return False, "missing_scope"
    if doc["approval_status"] in ["rejected", "outdated", "revoked"] or doc["validity_status"] in ["expired", "revoked"]:
        return False, "rejected_or_inactive_source"
    if context["environment"] == "corporate":
        if doc["approval_status"] != "approved" or doc["validity_status"] != "verified":
            return False, "not_institutionally_approved"
        if doc["source_availability"] != "available" or doc["document_hash"] is None:
            return False, "unverified_original"
        if ref.get("document_hash") != doc["document_hash"]:
            return False, "unverified_export_source_hash"
        if any(conflicts[cid]["severity"] in ["high", "critical"] and conflicts[cid]["status"] not in ["resolved", "rejected"] for cid in doc["identified_issues"]):
            return False, "unresolved_governance_issue"
    return True, "local_review_only" if doc["approval_status"] != "approved" else "approved"


def validate_export(export: dict, bundle: dict, allow_synthetic: bool = False) -> None:
    schema_check(export, bundle["schema"]["$defs"]["export"], bundle["schema"], "export")
    require(export["run_kind"] == "real" or (allow_synthetic and export["run_kind"] == "synthetic"), "Avaliador exige export de execução real; template/sintético não representa desempenho do RAG")
    require(export["executed_at"] is not None, "Execução exige data/hora real com fuso")
    require(export["dataset_version"] == bundle["registry"]["registry_version"], "Export pertence a outra versão do dataset")
    folder = bundle["folder"]
    for field, file in [("dataset_sha256", "rag_eval_dataset.jsonl"), ("evidence_catalog_sha256", "evidence_catalog.json"), ("document_registry_sha256", "document_registry.json"), ("conflicts_sha256", "conflicts.json"), ("card_coverage_sha256", "card_coverage.json")]:
        require(export[field] == sha256(folder/file), f"Export desatualizado: {field}")
    results = index_by(export["results"], "test_id")
    require(set(results) <= {c["test_id"] for c in bundle["cases"]}, "Export contém test_id desconhecido")
    require(bool(results), "Export vazio: nenhuma execução para avaliar")
    for result in results.values():
        require(result["retrieval_status"] == "observed" or not result["retrieved"], f"{result['test_id']}: recuperação não observada não pode conter candidatos")
        require(result["citation_status"] == "observed" or not result["citations"], f"{result['test_id']}: citações não observadas não podem conter referências")
        require((result["generation_status"] == "observed" and result["answer"] is not None)
                or (result["generation_status"] == "not_recorded" and result["answer"] is None and result["behavior"] is None), f"{result['test_id']}: estado de geração inconsistente")
        require(result["context_status"] == "observed" or all(v is None for v in result["context"].values()), f"{result['test_id']}: contexto não observado contém valores")


def average(values: list) -> float | None:
    observed = [value for value in values if value is not None]
    return sum(observed) / len(observed) if observed else None


def export_template(bundle: dict) -> dict:
    folder = bundle["folder"]
    return {"run_id":"PREENCHER_COM_EXECUCAO_REAL", "run_kind":"template",
        "dataset_version":bundle["registry"]["registry_version"],
        "dataset_sha256":sha256(folder/"rag_eval_dataset.jsonl"),
        "evidence_catalog_sha256":sha256(folder/"evidence_catalog.json"),
        "document_registry_sha256":sha256(folder/"document_registry.json"),
        "conflicts_sha256":sha256(folder/"conflicts.json"),
        "card_coverage_sha256":sha256(folder/"card_coverage.json"),
        "executed_at":None, "results":[]}


def evaluate(export: dict, bundle: dict, k: int = 3, allow_synthetic: bool = False) -> dict:
    require(type(k) is int and k > 0, "k deve ser inteiro positivo")
    validate_export(export, bundle, allow_synthetic)
    cases = index_by(bundle["cases"], "test_id")
    ev = index_by(bundle["evidence_catalog"]["evidence"], "evidence_id")
    docs = index_by(bundle["registry"]["documents"], "document_id")
    conflicts = index_by(bundle["conflicts"]["conflicts"], "conflict_id")
    details = []
    for result in export["results"]:
        case = cases[result["test_id"]]
        expected = []
        for eid in case["relevant_evidence_ids"]:
            target = reference(ev[eid])
            if target not in expected:
                expected.append(target)
        retrieved = result["retrieved"][:k]
        observed_retrieval = result["retrieval_status"] == "observed"
        retrieval = {"hit_at_k": None, "recall_at_k": None, "reciprocal_rank_at_k": None,
                     "document_match_at_k": None, "section_or_card_match_at_k": None}
        if observed_retrieval and expected:
            ranks = [i+1 for i, item in enumerate(retrieved) if any(reference_matches(item, target) for target in expected)]
            recall = sum(any(reference_matches(item, target) for item in retrieved) for target in expected) / len(expected)
            retrieval = {"hit_at_k": bool(ranks), "recall_at_k": recall,
                         "reciprocal_rank_at_k": 1/min(ranks) if ranks else 0,
                         "document_match_at_k": any(any(item["document_id"] == t["document_id"] and item["source_version"] == t["source_version"] for t in expected) for item in retrieved),
                         "section_or_card_match_at_k": bool(ranks)}
        generation_observed = result["generation_status"] == "observed"
        facts = [{"criterion_id": c["criterion_id"], "lexical_match": lexical_match(result["answer"], c)} for c in case["expected_facts"]] if generation_observed else []
        alerts = [c["criterion_id"] for c in case["forbidden_claims"] if lexical_match(result["answer"], c)] if generation_observed else []
        citations = result.get("citations", [])
        # Citations are an explicit observed trace, never inferred from answer text.
        observed_citations = result.get("citation_status") == "observed"
        matched_citations = [any(reference_matches(item, target) for target in case["expected_citation"]) for item in citations]
        citation_precision = sum(matched_citations)/len(citations) if observed_citations and citations else None
        citation_completeness = sum(any(reference_matches(item, target) for item in citations) for target in case["expected_citation"])/len(case["expected_citation"]) if observed_citations and case["expected_citation"] else None
        citation_policy_pass = (all(matched_citations) and all(any(reference_matches(item,t) for item in citations) for t in case["expected_citation"])) if observed_citations else None
        source_findings = []
        # Examine the full retrieved trace, not just @k: leaked unauthorized sources
        # below k must not disappear from the governance audit.
        for channel, values in [("retrieval", result["retrieved"]), ("citation", citations)]:
            for item in values:
                allowed, reason = source_allowed(item, case, docs, conflicts)
                if not allowed:
                    source_findings.append({"channel":channel, "document_id":item["document_id"], "reason":reason})
        both_source_channels_observed = observed_retrieval and observed_citations
        authorization_pass = not source_findings if both_source_channels_observed else False if source_findings else None
        context_observed = result["context_status"] == "observed"
        context_applicable = case["requires_context"] or case["expected_context"]["benefit_code"] is not None
        behavior_match = (result["behavior"] == case["expected_behavior"]) if generation_observed and result["behavior"] is not None else None
        details.append({"test_id":case["test_id"], "domain":case["domain"], "question_type":case["question_type"],
            "retrieval":retrieval, "generation_observed":generation_observed,
            "required_fact_checks":facts, "required_fact_lexical_coverage":sum(f["lexical_match"] for f in facts)/len(facts) if facts else None,
            "forbidden_claim_lexical_alerts":alerts, "forbidden_claims_semantic_verdict":"not_assessed",
            "citation_precision":citation_precision, "citation_completeness":citation_completeness,
            "citation_policy_pass":citation_policy_pass, "source_authorization_pass":authorization_pass,
            "source_findings":source_findings, "behavior_trace_match":behavior_match,
            "requires_context":case["requires_context"],
            "context_trace_match":result["context"] == case["expected_context"] if context_observed and context_applicable else None,
            "domain_trace_match":result["context"]["domain"] == case["expected_context"]["domain"] if context_observed and context_applicable else None,
            "card_trace_match":result["context"]["benefit_code"] == case["expected_context"]["benefit_code"] if context_observed and context_applicable else None,
            "expected_behavior":case["expected_behavior"],
            "documentary_fidelity":"not_assessed", "manual_review_required":True,
            "source_validation_status":case["validation_status"]})
    retrieval_cases = [d for d in details if d["retrieval"]["hit_at_k"] is not None]
    metrics = {name:average([d["retrieval"][field] for d in details]) for name,field in [
        ("hit_rate_at_k","hit_at_k"), ("recall_at_k","recall_at_k"), ("mrr_at_k","reciprocal_rank_at_k"),
        ("document_match_at_k","document_match_at_k"), ("section_or_card_match_at_k","section_or_card_match_at_k")]}
    metrics.update(required_fact_lexical_coverage=average([d["required_fact_lexical_coverage"] for d in details]),
                   citation_precision=average([d["citation_precision"] for d in details]),
                   citation_completeness=average([d["citation_completeness"] for d in details]))
    trace_fields = {"behavior_trace_match_rate":"behavior_trace_match", "context_trace_match_rate":"context_trace_match",
                    "domain_trace_match_rate":"domain_trace_match", "card_trace_match_rate":"card_trace_match",
                    "citation_policy_pass_rate":"citation_policy_pass", "source_authorization_pass_rate":"source_authorization_pass"}
    metrics.update({name:average([d[field] for d in details]) for name,field in trace_fields.items()})
    for label, behavior in [("fallback", "fallback"), ("clarification", "clarify")]:
        metrics[label+"_behavior_trace_match_rate"] = average([d["behavior_trace_match"] for d in details if d["expected_behavior"]==behavior])
    denominators = {name:sum(d["retrieval"]["hit_at_k"] is not None for d in details) for name in ["hit_rate_at_k","recall_at_k","mrr_at_k","document_match_at_k","section_or_card_match_at_k"]}
    for name in ["required_fact_lexical_coverage","citation_precision","citation_completeness"]:
        denominators[name] = sum(d[name] is not None for d in details)
    denominators.update({name:sum(d[field] is not None for d in details) for name,field in trace_fields.items()})
    for label,behavior in [("fallback","fallback"),("clarification","clarify")]:
        denominators[label+"_behavior_trace_match_rate"] = sum(d["behavior_trace_match"] is not None and d["expected_behavior"]==behavior for d in details)
    return {"report_kind":"real_export_deterministic_indicators" if export["run_kind"]=="real" else "synthetic_unit_test_only",
        "run_id":export["run_id"], "executed_at":export["executed_at"], "dataset_version":export["dataset_version"],
        "dataset_sha256":export["dataset_sha256"], "k":k,
        "coverage":{"dataset_cases":len(cases),"exported_cases":len(details),"missing_test_ids":sorted(set(cases)-{r['test_id'] for r in export['results']}),"retrieval_metric_denominator":len(retrieval_cases),"generation_observed":sum(d['generation_observed'] for d in details)},
        "metrics":metrics, "metric_denominators":denominators, "aggregation":"macro_average_over_observed_applicable_cases", "cases":details, "documentary_fidelity":"not_assessed",
        "provenance_hashes":{key:export[key] for key in ["evidence_catalog_sha256","document_registry_sha256","conflicts_sha256","card_coverage_sha256"]},
        "evaluator_sha256":sha256(Path(__file__)), "evaluation_schema_sha256":sha256(bundle["folder"]/"evaluation_schema.json"),
        "limitation":"Indicadores lexicais não comprovam fidelidade, ausência de alucinação, negação correta ou aprovação institucional. Não há score geral de precisão. Identificação de run_kind é declarada pelo exportador, não prova criptográfica de execução.",
        "model_execution_by_this_tool":"never"}


def main(argv=None) -> int:
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="MilioAI: avaliação/governança offline, sem serviços")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validar estrutura, critérios, referências, hashes e cobertura")
    commands.add_parser("render-views", help="Gerar CSV/Markdown derivados, sem alterar aprovações")
    template = commands.add_parser("template", help="Gerar template vazio com hashes atuais; não produz scores")
    template.add_argument("--output", type=Path)
    evaluation = commands.add_parser("evaluate", help="Ler export local de execução real; nunca executar modelo")
    evaluation.add_argument("results", type=Path)
    evaluation.add_argument("--k", type=int, default=3)
    evaluation.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        bundle = load_bundle()
        summary = validate_bundle(bundle, check_views=args.command != "render-views")
        if args.command == "render-views":
            (HERE/"validation_registry.csv").write_text(csv_view(bundle), encoding="utf-8")
            (HERE/"conflicts.md").write_text(conflicts_view(bundle), encoding="utf-8")
            report = {"status":"views_rendered", "files":["validation_registry.csv","conflicts.md"], "approval_changes":False}
        elif args.command == "template":
            report = export_template(bundle)
        elif args.command == "evaluate":
            report = evaluate(read_json(args.results), bundle, args.k)
        else:
            report = summary
        if args.command in ["template", "evaluate"] and args.output:
            protected = [HERE/name for name in [*ARTIFACT_FILES.values(), "evaluation_schema.json", "rag_eval_dataset.jsonl", "validation_registry.csv", "conflicts.md", "quality.py", "README.md", "evaluation_report.md"]]
            if args.command == "evaluate":
                protected += [HERE/"results_template.json", args.results]
            require(args.output.resolve() not in [p.resolve() for p in protected], "Saída não pode sobrescrever artefatos de governança ou o export de entrada")
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    except (QualityError, OSError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

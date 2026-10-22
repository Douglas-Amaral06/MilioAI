"""Conservative rule gate before entailment. Uncertainty never overrides a contradiction.

Protected instructions may be quoted from the source. Paraphrases that cannot be
resolved deterministically proceed only if they preserve every source qualifier.
For high-risk structured rules we require the intact documentary span instead.
"""

import re

from app.support.exact import cited_pairs, folded, plain, validate_exact


def rule_issues(claim, evidence):
    claim, evidence = folded(plain(claim)), folded(plain(evidence))
    # Verbatim documentary spans retain their conditions and modality.
    rules = re.split(r"(?<=[.!?])\s+|\s*[•]\s*", evidence)
    if claim.strip(' ."“”') == evidence.strip(' ."“”') or any(
        claim.strip(' ."“”') == r.strip(' ."“”') for r in rules
    ):
        return []
    issues = []
    # Relative time is an exact fact too. A procedural claim cannot borrow a
    # citation that merely describes the purpose of a document.
    for marker in re.findall(r"\b(hoje|amanha|ontem|imediatamente)\b", claim):
        if not re.search(r"\b" + marker + r"\b", evidence):
            issues.append("unsupported_relative_deadline")
    action_families = [
        r"envi\w*|encaminh\w*|entreg\w*",
        r"assin\w*",
        r"preench\w*|registr\w*|lanc\w*",
        r"pag\w*|quit\w*",
        r"bloque\w*",
        r"retir\w*",
    ]
    for actions in action_families:
        if re.search(r"\b(?:" + actions + r")\b", claim) and not re.search(
            r"\b(?:" + actions + r")\b", evidence
        ):
            issues.append("action_absent_from_cited_evidence")
    for rule in rules:
        # Compare action AND object. A shared label alone is not a contradiction.
        words = set(re.findall(r"[a-z]{4,}", rule)) - {
            "para",
            "como",
            "caso",
            "quando",
            "deve",
            "pode",
            "somente",
            "exceto",
            "folha",
            "ponto",
        }
        overlap = words & set(re.findall(r"[a-z]{4,}", claim))
        if len(overlap) < 2:
            continue
        if re.search(r"\b(nao|nunca|proibid\w*)\b", rule):
            prohibited = re.search(r"\b(?:nao|nunca)\s+(?:se\s+)?([a-z]+)", rule)
            if prohibited and prohibited[1] not in {"ocorra", "ha", "e", "seja"}:
                stem = re.escape(prohibited[1][:5])
                negative_action = re.search(
                    r"\b(?:nao|nunca)\s+(?:(?:deve|devera|pode|podera|se|e permitido|e recomendado|precisa)\s+){0,2}"
                    + stem
                    + r"\w*|\bevit\w*\s+"
                    + stem
                    + r"\w*",
                    claim,
                )
            else:
                negative_action = re.search(r"\b(nao|nunca|proibid\w*|evit\w*)\b", claim)
            if not negative_action:
                issues.append("prohibition_inverted")
        if re.search(r"\b(pode|podera|permitid\w*)\b", rule) and re.search(
            r"\b(deve|devera|obrigatori\w*|sempre)\b", claim
        ):
            issues.append("permission_strengthened")
        if re.search(r"\b(deve|devera|obrigatori\w*)\b", rule) and re.search(
            r"dispensad\w*|opcional|nao precisa|nao e necessar", claim
        ):
            issues.append("implicit_obligation_inversion")
        qualifiers = [
            r"\bse\b",
            r"\bcaso\b",
            r"\bquando\b",
            r"\bsomente\b",
            r"\bexceto\b",
            r"\bsalvo\b",
            r"\bdesde que\b",
        ]
        for qualifier in qualifiers:
            if re.search(qualifier, rule) and not re.search(qualifier, claim):
                issues.append("condition_or_exception_missing")
        if re.search(r"\butei[sl]\b|\butil\b", rule) and re.search(r"\bcorrid\w*\b", claim):
            issues.append("deadline_unit_changed")
        # Action/condition/object contract, independent of a particular label.
        required = re.search(
            r"(?:manter|mantenha)\s+(?:o\s+)?(?:preenchimento|registro)\s+(?:como\s+)?([a-z]+)",
            rule,
        )
        if required and re.search(r"\b(caso|se|quando)\b", rule):
            if re.search(
                r"tro[cq]\w*|substitu\w*|nao.*(?:manter|mantenha|registr)|(?:registr|preench|escrev|colo[cq])\w*",
                claim,
            ):
                if rule.strip(" .") not in claim:
                    issues.append("conditional_action_object_uncertain")
    return sorted(set(issues))


def deterministic_grounding(answer, chunks):
    from app.support.knowledge import bound_rules

    for claim, cited in cited_pairs(answer, chunks):
        evidence = " ".join(c["excerpt"] for c in cited)
        validate_exact(claim, evidence)
        for rule in bound_rules(cited):
            # Bind restrictions only to identical source version AND content hash.
            if any(re.search(pattern, folded(claim)) for pattern in rule["claim_triggers"]):
                if folded(plain(rule["documentary_text"])) not in folded(plain(claim)):
                    raise ValueError(
                        "Structured rule requires intact condition/action/object: " + rule["id"]
                    )
        issues = rule_issues(claim, evidence)
        if issues:
            raise ValueError("Rule contradiction or uncertainty: " + ",".join(issues))

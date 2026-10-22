"""Auditable summaries of real exports. Never runs a model or changes source versions."""

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

import quality


def location_match(actual, target):
    """Cross-version location indicator only; deliberately NOT evidence equivalence."""
    if any(actual.get(k) != target.get(k) for k in ("document_id", "page", "benefit_code")):
        return False
    if target["benefit_code"] is not None:
        section = actual.get("section_or_row")
        match = re.match(r"^\s*(\d+)(?:\s*[·.:-]|$)", section or "")
        return section is None or bool(match and match[1] == target["benefit_code"])
    return quality.section_key(actual.get("section_or_row")) == quality.section_key(
        target["section_or_row"]
    )


def latency(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "n": len(values),
        "mean_ms": round(sum(values) / len(values)),
        "p50_ms": values[(len(values) - 1) // 2],
        "p95_ms": values[math.ceil(len(values) * 0.95) - 1],
        "max_ms": max(values),
    }


def summarize(folder, package):
    bundle = quality.load_bundle(package)
    export = quality.read_json(folder / "results.json")
    report = quality.evaluate(export, bundle)
    cases = {c["test_id"]: c for c in bundle["cases"]}
    evidence = {e["evidence_id"]: e for e in bundle["evidence_catalog"]["evidence"]}
    raw = {p.stem: quality.read_json(p) for p in (folder / "cases").glob("*.json")}
    results = {r["test_id"]: r for r in export["results"]}
    overrides = (
        quality.read_json(folder / "review-overrides.json")
        if (folder / "review-overrides.json").exists()
        else {}
    )
    details, integrity, logs = [], [], []
    for item in report["cases"]:
        test_id = item["test_id"]
        case, result, observation = cases[test_id], results[test_id], raw[test_id]
        turn = observation["turns"][-1]
        expected = []
        for eid in case["relevant_evidence_ids"]:
            ref = quality.reference(evidence[eid])
            if ref["document_id"] in {"folha-ponto", "vt-segunda-via"} and ref not in expected:
                expected.append(ref)
        ranks = [
            i + 1
            for i, ref in enumerate(result["retrieved"][:3])
            if any(location_match(ref, target) for target in expected)
        ]
        location = (
            {
                "hit_at_3": bool(ranks),
                "recall_at_3": sum(
                    any(location_match(ref, target) for ref in result["retrieved"][:3])
                    for target in expected
                )
                / len(expected),
                "reciprocal_rank_at_3": 1 / min(ranks) if ranks else 0,
            }
            if expected and result["retrieval_status"] == "observed"
            else {"hit_at_3": None, "recall_at_3": None, "reciprocal_rank_at_3": None}
        )
        cite_targets = case["expected_citation"]
        citation_location = (
            sum(
                any(location_match(ref, target) for ref in result["citations"])
                for target in cite_targets
            )
            / len(cite_targets)
            if cite_targets and result["citation_status"] == "observed"
            else None
        )
        errors = turn.get("error") or [e for e in turn.get("events", []) if e["event"] == "error"]
        final = next((e["message"] for e in turn.get("events", []) if e["event"] == "done"), None)
        source_ids = {
            c["id"] for call in turn.get("retrieval_calls", []) for c in call.get("chunks", [])
        }
        stream_equal = (
            final is not None
            and "".join(e.get("text", "") for e in turn["events"] if e["event"] == "delta")
            == final["content"]
        )
        source_membership = final is not None and all(
            s["id"] in source_ids for s in final["sources"]
        )
        exact_input = turn["payload"]["content"] == case["question"]
        aliases = {
            f"F{i + 1}"
            for i, c in enumerate(turn.get("final_state", {}).get("chunks", []))
            if final and c["id"] in {s["id"] for s in final["sources"]}
        }
        markers = re.findall(r"\[fonte:([^]]+)\]", final["content"]) if final else []
        resolved_markers = final is not None and all(
            marker in aliases or marker in {s["id"] for s in final["sources"]} for marker in markers
        )
        integrity.append(
            {
                "test_id": test_id,
                "exact_question": exact_input,
                "stream_matches_final": stream_equal,
                "sources_were_retrieved": source_membership,
                "citation_markers_resolve": resolved_markers,
                "has_completed_response": final is not None,
            }
        )
        reasons = []
        review_alerts = []
        if errors:
            reasons.append("runtime_error")
        if item["behavior_trace_match"] is False:
            if result["behavior"] == "surface_conflict" and case["expected_behavior"] == "answer":
                review_alerts.append(
                    "answer_includes_explicit_review_notice; behavior_taxonomy_needs_review"
                )
            else:
                reasons.append("behavior_mismatch")
        if item["context_trace_match"] is False:
            reasons.append("context_mismatch")
        if expected and location["hit_at_3"] is False:
            reasons.append("expected_location_not_retrieved")
        if cite_targets and citation_location == 0:
            reasons.append("expected_citation_location_missing")
        if final and (not stream_equal or not source_membership or not resolved_markers):
            reasons.append("trace_integrity_failure")
        logs.extend(
            {"test_id": test_id, "turn_kind": t["kind"], **entry}
            for t in observation["turns"]
            for entry in t.get("logs", [])
        )
        all_facts_lexical = item["required_fact_lexical_coverage"] == 1
        automatic = (
            "failed_checks"
            if reasons
            else "passed_checks"
            if all_facts_lexical
            and not item["forbidden_claim_lexical_alerts"]
            and not review_alerts
            else "inconclusive_checks"
        )
        override = overrides.get(test_id)
        if override:
            quality.require(
                override["status"] == "reprovado"
                and override["observed_answer"] == result["answer"],
                "Review override must match the exact observed answer and cannot approve semantics",
            )
            reasons.append(override["reason"])
        # Passing lexical checks never approves semantics. Corporate policy is not a deployment test.
        verdict = "reprovado" if reasons else "inconclusivo"
        details.append(
            {
                "test_id": test_id,
                "domain": case["domain"],
                "automatic_status": automatic,
                "final_status": verdict,
                "reasons": reasons,
                "review_alerts": review_alerts,
                "review_override": override,
                "location_only": location,
                "citation_location_completeness": citation_location,
                "strict_version_metrics": item["retrieval"],
                "required_fact_lexical_coverage": item["required_fact_lexical_coverage"],
                "forbidden_lexical_alerts": item["forbidden_claim_lexical_alerts"],
                "behavior": result["behavior"],
                "behavior_match": item["behavior_trace_match"],
                "context_match": item["context_trace_match"],
                "card_match": item["card_trace_match"],
                "question_duration_ms": turn["duration_ms"],
                "total_case_duration_ms": observation["duration_ms"],
                "production_deployment_assessed": False
                if case["run_context"]["environment"] == "corporate"
                else None,
                "manual_semantic_review": "pending",
            }
        )
    by_domain = {}
    for domain in sorted({c["domain"] for c in bundle["cases"]}):
        subset = [d for d in details if d["domain"] == domain]
        canonical_subset = [d for d in report["cases"] if d["domain"] == domain]
        by_domain[domain] = {
            "executed": len(subset),
            "statuses": dict(Counter(d["final_status"] for d in subset)),
            "automatic_statuses": dict(Counter(d["automatic_status"] for d in subset)),
            "location_only_metrics": {
                name: {
                    "value": quality.average([d["location_only"][field] for d in subset]),
                    "n": sum(d["location_only"][field] is not None for d in subset),
                }
                for name, field in [
                    ("hit_rate_at_3", "hit_at_3"),
                    ("recall_at_3", "recall_at_3"),
                    ("mrr_at_3", "reciprocal_rank_at_3"),
                ]
            },
            "strict_metrics": {
                name: {
                    "value": quality.average([d["retrieval"][field] for d in canonical_subset]),
                    "n": sum(d["retrieval"][field] is not None for d in canonical_subset),
                }
                for name, field in [
                    ("hit_rate_at_3", "hit_at_k"),
                    ("recall_at_3", "recall_at_k"),
                    ("mrr_at_3", "reciprocal_rank_at_k"),
                ]
            },
            "required_fact_lexical_coverage": quality.average(
                [d["required_fact_lexical_coverage"] for d in subset]
            ),
            "citation_location_completeness": quality.average(
                [d["citation_location_completeness"] for d in subset]
            ),
            "behavior_match": quality.average([d["behavior_match"] for d in subset]),
            "context_match": quality.average([d["context_match"] for d in subset]),
            "card_match": quality.average([d["card_match"] for d in subset]),
            "latency_question": latency([d["question_duration_ms"] for d in subset]),
            "latency_with_context": latency([d["total_case_duration_ms"] for d in subset]),
        }
    return {
        "run_id": export["run_id"],
        "counts": {
            "dataset": len(cases),
            "executed": len(details),
            "approved_semantically": 0,
            "failed_observable_checks": sum(d["final_status"] == "reprovado" for d in details),
            "inconclusive_semantics": sum(d["final_status"] == "inconclusivo" for d in details),
            "not_executed": len(cases) - len(details),
        },
        "automatic_statuses": dict(Counter(d["automatic_status"] for d in details)),
        "by_domain": by_domain,
        "strict_metrics": report["metrics"],
        "strict_metric_denominators": report["metric_denominators"],
        "failure_categories": dict(Counter(reason for d in details for reason in d["reasons"])),
        "runtime_event_counts": dict(Counter(entry["event"] for entry in logs)),
        "grounding_events": [entry for entry in logs if "grounding" in entry["event"]],
        "failure_events": [
            entry
            for entry in logs
            if entry["event"]
            in {
                "response_failed",
                "generation_failed",
                "evidence_assessment_failed",
                "embedding_failed",
                "intent_failed",
            }
        ],
        "integrity": integrity,
        "cases": details,
        "limitations": [
            "Location-only metrics ignore version; they do not establish snapshot equivalence or semantic support.",
            "Lexical checks cannot approve semantic fidelity or absence of hallucination.",
            "Corporate cases exercise production document filtering inside development; production authentication/deployment is not assessed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    result = summarize(args.run, Path(__file__).resolve().parent)
    (args.run / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = [
        "test_id",
        "domain",
        "final_status",
        "automatic_status",
        "reasons",
        "review_alerts",
        "behavior",
        "context_match",
        "question_duration_ms",
        "total_case_duration_ms",
    ]
    with (args.run / "case-verdicts.csv").open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for item in result["cases"]:
            writer.writerow(
                {
                    key: " | ".join(item[key]) if isinstance(item[key], list) else item[key]
                    for key in fields
                }
            )
    print(
        json.dumps(
            {"counts": result["counts"], "by_domain": result["by_domain"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

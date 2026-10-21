"""Synthetic unit inputs validate mathematics/guards, never measure a real RAG."""
import copy
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FOLDER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rag_quality_offline", FOLDER / "quality.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def exported(bundle, test_id="FP-02", **changes):
    case = next(c for c in bundle["cases"] if c["test_id"] == test_id)
    result = {"test_id":test_id, "retrieval_status":"observed", "retrieved":copy.deepcopy(case["expected_citation"]),
        "citation_status":"observed", "citations":copy.deepcopy(case["expected_citation"]),
        "generation_status":"observed", "answer":"Resposta de teste sintético, sem validade institucional.",
        "behavior":case["expected_behavior"], "context_status":"observed", "context":copy.deepcopy(case["expected_context"])}
    result.update(changes)
    return {"run_id":"SYNTHETIC-UNIT-TEST-ONLY", "run_kind":"synthetic", "executed_at":"2026-10-20T12:00:00Z",
        "dataset_version":bundle["registry"]["registry_version"],
        "dataset_sha256":q.sha256(FOLDER / "rag_eval_dataset.jsonl"),
        "evidence_catalog_sha256":q.sha256(FOLDER / "evidence_catalog.json"),
        "document_registry_sha256":q.sha256(FOLDER / "document_registry.json"),
        "conflicts_sha256":q.sha256(FOLDER / "conflicts.json"),
        "card_coverage_sha256":q.sha256(FOLDER / "card_coverage.json"), "results":[result]}


class ArtifactValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = q.load_bundle(FOLDER)

    def setUp(self):
        self.b = copy.deepcopy(self.bundle)

    def validate(self):
        return q.validate_bundle(self.b, check_views=False)

    def test_full_artifact_bundle_and_coverage(self):
        report = q.validate_bundle(self.b)
        self.assertEqual(report["cases"], 76)
        self.assertEqual(report["card_coverage"]["covered"], 33)
        self.assertEqual(report["card_coverage"]["pages"], {1:24,2:9})
        self.assertEqual(report["approved_documents"], 0)
        self.assertEqual(report["rag_performance"], "not_measured")

    def test_duplicate_case_and_evidence_ids(self):
        for key, rows in [("cases",None),("evidence_catalog","evidence")]:
            with self.subTest(key=key):
                self.b = copy.deepcopy(self.bundle)
                values = self.b[key] if rows is None else self.b[key][rows]
                values.append(copy.deepcopy(values[0]))
                with self.assertRaisesRegex(q.QualityError,"duplicados"):
                    self.validate()

    def test_required_fields_and_empty_criteria(self):
        del self.b["cases"][0]["question"]
        with self.assertRaisesRegex(q.QualityError,"obrigatórios"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["cases"][0]["expected_facts"] = []
        with self.assertRaisesRegex(q.QualityError,"insuficientes"):
            self.validate()

    def test_duplicate_json_keys_nonfinite_values_and_blank_lines(self):
        for text in ['{"id":1,"id":2}', '{"score":NaN}', '{"score":Infinity}']:
            with self.subTest(text=text), self.assertRaises(q.QualityError):
                q.parse_json(text,"test")
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            for file in [*q.ARTIFACT_FILES.values(),"evaluation_schema.json","rag_eval_dataset.jsonl"]:
                (target/file).write_bytes((FOLDER/file).read_bytes())
            with (target/"rag_eval_dataset.jsonl").open("a",encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(q.QualityError,"linha vazia"):
                q.load_bundle(target)

    def test_references_and_criteria_must_resolve(self):
        self.b["cases"][0]["relevant_evidence_ids"] = ["unknown"]
        with self.assertRaisesRegex(q.QualityError,"evidência inexistente"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["cases"][0]["expected_facts"][0]["evidence_ids"] = ["vt-89"]
        with self.assertRaisesRegex(q.QualityError,"critério sem evidência"):
            self.validate()

    def test_invalid_page_zero_out_of_range_and_bool(self):
        for value in [0,3,True]:
            with self.subTest(page=value):
                self.b = copy.deepcopy(self.bundle)
                self.b["evidence_catalog"]["evidence"][0]["page"] = value
                with self.assertRaises(q.QualityError):
                    self.validate()

    def test_unknown_document_and_unknown_approval_state(self):
        self.b["evidence_catalog"]["evidence"][0]["document_id"] = "unknown"
        with self.assertRaisesRegex(q.QualityError,"documento inexistente"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["registry"]["documents"][0]["approval_status"] = "auto_approved"
        with self.assertRaisesRegex(q.QualityError,"estado/valor"):
            self.validate()

    def test_cannot_fabricate_original_hash_or_approval(self):
        self.b["registry"]["documents"][0]["document_hash"] = "a"*64
        with self.assertRaisesRegex(q.QualityError,"inventado"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["registry"]["documents"][0]["approval_status"] = "approved"
        with self.assertRaisesRegex(q.QualityError,"original ausente"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["registry"]["documents"][2]["approval_status"] = "approved"
        with self.assertRaisesRegex(q.QualityError,"revisor, data"):
            self.validate()

    def test_cannot_resolve_conflict_without_institutional_record(self):
        self.b["conflicts"]["conflicts"][0]["status"] = "resolved"
        with self.assertRaisesRegex(q.QualityError,"registro institucional"):
            self.validate()

    def test_card_code_and_case_coverage_must_agree(self):
        self.b["coverage"]["cards"][0]["benefit_code"] = "999999"
        with self.assertRaises(q.QualityError):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["coverage"]["cards"][0]["test_ids"] = ["FP-01"]
        with self.assertRaisesRegex(q.QualityError,"cobertura de casos"):
            self.validate()

    def test_citation_and_main_reference_cannot_be_fabricated(self):
        self.b["cases"][0]["expected_page"] = 2
        with self.assertRaisesRegex(q.QualityError,"referência principal"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        self.b["cases"][0]["expected_citation"][0]["section_or_row"] = "6."
        with self.assertRaisesRegex(q.QualityError,"citação sem evidência"):
            self.validate()

    def test_conversational_context_and_categories_are_required(self):
        case = next(c for c in self.b["cases"] if c["test_id"]=="CTX-01")
        case["conversation_context"]["prior_turns"] = []
        with self.assertRaisesRegex(q.QualityError,"contexto incompleto"):
            self.validate()
        self.b = copy.deepcopy(self.bundle)
        for c in self.b["cases"]:
            if c["question_type"]=="semantic_paraphrase": c["question_type"]="direct"
        with self.assertRaisesRegex(q.QualityError,"Categorias sem cobertura"):
            self.validate()

    def test_csv_markdown_views_and_hashes_are_checked(self):
        with tempfile.TemporaryDirectory() as name:
            self.b["folder"] = Path(name)
            with self.assertRaisesRegex(q.QualityError,"visão desatualizada"):
                q.validate_bundle(self.b)
        self.b = copy.deepcopy(self.bundle)
        self.b["evidence_catalog"]["evidence"][0]["excerpt"] += " altered"
        with self.assertRaisesRegex(q.QualityError,"hash do trecho"):
            self.validate()

    def test_dates_and_local_schema_references_fail_closed(self):
        self.b["registry"]["technical_inspection_date"] = "2026-02-30"
        with self.assertRaisesRegex(q.QualityError,"data/hora"):
            self.validate()
        schema = copy.deepcopy(self.bundle["schema"])
        schema["$defs"]["export"]["properties"]["results"]["items"]["$ref"] = "https://invalid.example/schema"
        with self.assertRaisesRegex(q.QualityError,"remota"):
            q.schema_definition_check(schema,schema)
        schema = copy.deepcopy(self.bundle["schema"])
        schema["$defs"]["export"]["unsupportedKeyword"] = True
        with self.assertRaisesRegex(q.QualityError,"keyword"):
            q.schema_definition_check(schema,schema)

    def test_relative_paths_cannot_escape_workspace(self):
        for value in ["../secret", "https://example.com", "C:/secret", "//server/share", "a\\b"]:
            with self.subTest(value=value), self.assertRaises(q.QualityError):
                q.safe_path(q.ROOT,value)

    def test_incomplete_card_fields_and_untraceable_facts_fail(self):
        card=self.b["coverage"]["cards"][0]
        ev=next(e for e in self.b["evidence_catalog"]["evidence"] if e["evidence_id"]==card["evidence_id"])
        del ev["observed_fields"]["fee"]
        with self.assertRaisesRegex(q.QualityError,"cartão incompleto"):
            self.validate()
        self.b=copy.deepcopy(self.bundle)
        self.b["cases"][0]["expected_facts"][0]["evidence_ids"]=[]
        with self.assertRaisesRegex(q.QualityError,"exigem evidência"):
            self.validate()

    def test_aliases_cannot_be_only_whitespace_or_punctuation(self):
        self.b["cases"][0]["expected_facts"][0]["match"]["all_of"]=[["---"]]
        with self.assertRaisesRegex(q.QualityError,"após normalização"):
            self.validate()

    def test_no_network_or_application_imports(self):
        with patch.object(socket,"socket",side_effect=AssertionError("network forbidden")), patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")):
            loaded = q.load_bundle(FOLDER)
            q.validate_bundle(loaded)
            q.evaluate(exported(loaded),loaded,allow_synthetic=True)
        for module in ["fastapi","langgraph","httpx","sqlalchemy","ollama","supabase"]:
            self.assertNotIn(module,sys.modules)


class DeterministicEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = q.load_bundle(FOLDER)

    def score(self,payload,k=3):
        return q.evaluate(payload,self.b,k,allow_synthetic=True)

    def test_hit_recall_mrr_and_duplicate_targets(self):
        payload=exported(self.b)
        target=copy.deepcopy(payload["results"][0]["retrieved"][0])
        wrong={**target,"section_or_row":"1."}
        payload["results"][0]["retrieved"]=[wrong,target,target]
        report=self.score(payload)
        self.assertEqual(report["metrics"]["hit_rate_at_k"],1)
        self.assertEqual(report["metrics"]["recall_at_k"],1)
        self.assertEqual(report["metrics"]["mrr_at_k"],.5)
        self.assertEqual(self.score(payload,k=1)["metrics"]["hit_rate_at_k"],0)
        self.assertEqual(report["report_kind"],"synthetic_unit_test_only")

    def test_recall_uses_unique_document_section_targets(self):
        payload=exported(self.b,"CONFLICT-01")
        payload["results"][0]["retrieved"]=payload["results"][0]["retrieved"][:1]*3
        self.assertEqual(self.score(payload)["metrics"]["recall_at_k"],.5)

    def test_wrong_card_wrong_page_and_version_do_not_count_as_evidence_hit(self):
        for change in [{"benefit_code":"472","section_or_row":"472"},{"section_or_row":"472 · Wrong"},{"page":1},{"source_version":"obsolete"}]:
            with self.subTest(change=change):
                payload=exported(self.b,"VT-89")
                payload["results"][0]["retrieved"][0].update(change)
                self.assertEqual(self.score(payload)["metrics"]["hit_rate_at_k"],0)

    def test_numbered_sections_match_real_chunk_titles(self):
        payload=exported(self.b)
        payload["results"][0]["retrieved"][0]["section_or_row"]="2. Periodicidade e Prazo"
        self.assertEqual(self.score(payload)["metrics"]["hit_rate_at_k"],1)

    def test_missing_observations_are_not_scored_as_zero(self):
        payload=exported(self.b,retrieval_status="not_recorded",retrieved=[],generation_status="not_recorded",answer=None,behavior=None,citation_status="not_recorded",citations=[],context_status="not_recorded",context={"domain":None,"benefit_code":None})
        report=self.score(payload)
        self.assertIsNone(report["metrics"]["hit_rate_at_k"])
        self.assertIsNone(report["metrics"]["required_fact_lexical_coverage"])
        self.assertIsNone(report["cases"][0]["source_authorization_pass"])
        self.assertEqual(report["coverage"]["retrieval_metric_denominator"],0)
        self.assertEqual(len(report["coverage"]["missing_test_ids"]),75)

    def test_observed_empty_retrieval_is_miss_not_unobserved(self):
        report=self.score(exported(self.b,retrieved=[]))
        self.assertEqual(report["metrics"]["hit_rate_at_k"],0)
        self.assertEqual(report["coverage"]["retrieval_metric_denominator"],1)

    def test_normalized_criteria_allow_paraphrases_but_not_whole_answer_equality(self):
        for text in ["A entrega ocorre no SEGUNDO DIA ÚTIL do mês, conforme material pendente de validação.", "Até o 2º dia útil do mês. Vigência não verificada."]:
            with self.subTest(text=text):
                report=self.score(exported(self.b,answer=text))
                self.assertEqual(report["metrics"]["required_fact_lexical_coverage"],1)

    def test_lexical_match_cannot_prove_fidelity_or_resolve_negation(self):
        report=self.score(exported(self.b,answer="Não é o segundo dia corrido. O segundo dia útil do mês exige vigência não confirmada."))
        case=report["cases"][0]
        self.assertTrue(case["forbidden_claim_lexical_alerts"])
        self.assertEqual(case["forbidden_claims_semantic_verdict"],"not_assessed")
        self.assertEqual(case["documentary_fidelity"],"not_assessed")
        self.assertTrue(case["manual_review_required"])

    def test_citations_require_document_page_section_and_version(self):
        payload=exported(self.b)
        payload["results"][0]["citations"][0]["page"]=2
        case=self.score(payload)["cases"][0]
        self.assertEqual(case["citation_precision"],0)
        self.assertFalse(case["citation_policy_pass"])

    def test_source_authorization_catches_pending_corporate_and_missing_scope(self):
        for tid,source_case in [("AUTH-01","FP-02"),("AUTH-02","VT-89"),("AUTH-03","OP-03"),("AUTH-04","OP-01")]:
            with self.subTest(tid=tid):
                payload=exported(self.b,tid)
                source=exported(self.b,source_case)["results"][0]["retrieved"][0]
                payload["results"][0]["retrieved"]=[source]
                case=self.score(payload)["cases"][0]
                self.assertFalse(case["source_authorization_pass"])
                self.assertTrue(case["source_findings"])

    def test_unknown_source_below_k_is_audited(self):
        payload=exported(self.b)
        extra=copy.deepcopy(payload["results"][0]["retrieved"][0]); extra["document_id"]="unregistered"
        payload["results"][0]["retrieved"].append(extra)
        case=self.score(payload,k=1)["cases"][0]
        self.assertEqual(case["retrieval"]["hit_at_k"],1)
        self.assertFalse(case["source_authorization_pass"])

    def test_fallback_cannot_cite_unexpected_document(self):
        payload=exported(self.b,"NEG-02")
        payload["results"][0]["citations"] = exported(self.b,"VT-89")["results"][0]["citations"]
        case=self.score(payload)["cases"][0]
        self.assertFalse(case["citation_policy_pass"])
        self.assertFalse(case["source_authorization_pass"])

    def test_context_and_behavior_require_observed_trace(self):
        payload=exported(self.b,"CTX-09")
        payload["results"][0]["context"]["benefit_code"]="89"
        self.assertFalse(self.score(payload)["cases"][0]["context_trace_match"])
        payload["results"][0].update(context_status="not_recorded",context={"domain":None,"benefit_code":None},behavior=None)
        case=self.score(payload)["cases"][0]
        self.assertIsNone(case["context_trace_match"])
        self.assertIsNone(case["behavior_trace_match"])

    def test_exports_reject_duplicate_unknown_ids_stale_hashes_and_invalid_states(self):
        payload=exported(self.b)
        payload["results"].append(copy.deepcopy(payload["results"][0]))
        with self.assertRaisesRegex(q.QualityError,"duplicados"):
            self.score(payload)
        payload=exported(self.b); payload["results"][0]["test_id"]="UNKNOWN"
        with self.assertRaisesRegex(q.QualityError,"desconhecido"):
            self.score(payload)
        payload=exported(self.b); payload["dataset_sha256"]="0"*64
        with self.assertRaisesRegex(q.QualityError,"desatualizado"):
            self.score(payload)
        payload=exported(self.b,retrieval_status="not_recorded")
        with self.assertRaisesRegex(q.QualityError,"não observada"):
            self.score(payload)

    def test_cli_rejects_templates_and_synthetic_reports(self):
        result=subprocess.run([sys.executable,str(FOLDER/"quality.py"),"evaluate",str(FOLDER/"results_template.json")],capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(result.returncode,1)
        self.assertIn("execução real",result.stderr)
        with self.assertRaisesRegex(q.QualityError,"execução real"):
            q.evaluate(exported(self.b),self.b)

    def test_schema_is_enforced_for_citation_trace_and_k(self):
        payload=exported(self.b); del payload["results"][0]["citation_status"]
        with self.assertRaisesRegex(q.QualityError,"obrigatórios"):
            self.score(payload)
        for k in [0,-1,True]:
            with self.subTest(k=k), self.assertRaises(q.QualityError):
                self.score(exported(self.b),k)

    def test_template_uses_current_bindings_and_never_fabricates_execution_date(self):
        template=q.export_template(self.b)
        self.assertEqual(template["run_kind"],"template")
        self.assertIsNone(template["executed_at"])
        self.assertEqual(template["results"],[])
        q.schema_check(template,self.b["schema"]["$defs"]["export"],self.b["schema"])
        self.assertEqual(template,q.read_json(FOLDER/"results_template.json"))

    def test_original_document_hash_is_not_interchangeable_with_chunk_hash(self):
        case=next(c for c in self.b["cases"] if c["test_id"]=="OP-01")
        docs=q.index_by(self.b["registry"]["documents"],"document_id")
        conflicts=q.index_by(self.b["conflicts"]["conflicts"],"conflict_id")
        ref=copy.deepcopy(case["expected_citation"][0]); ref["document_hash"]="f"*64
        self.assertEqual(q.source_allowed(ref,case,docs,conflicts),(False,"source_hash_mismatch"))
        docs=copy.deepcopy(docs); doc=docs["operational-services"]
        doc.update(approval_status="approved",validity_status="verified",identified_issues=[])
        corporate=copy.deepcopy(case); corporate["run_context"]["environment"]="corporate"
        ref.pop("document_hash"); ref["chunk_hash"]=doc["document_hash"]
        self.assertEqual(q.source_allowed(ref,corporate,docs,conflicts),(False,"unverified_export_source_hash"))

    def test_unknown_execution_time_and_governance_hash_changes_are_rejected(self):
        payload=exported(self.b); payload["executed_at"]=None
        with self.assertRaisesRegex(q.QualityError,"data/hora real"):
            self.score(payload)
        payload=exported(self.b); payload["conflicts_sha256"]="f"*64
        with self.assertRaisesRegex(q.QualityError,"desatualizado"):
            self.score(payload)


if __name__ == "__main__":
    unittest.main()

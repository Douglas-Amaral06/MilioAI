from copy import deepcopy

from app.rag.evaluate_real import PolicySettings, export_result, inputs


def test_execution_inputs_never_include_expected_answers():
    case = {
        "test_id": "X-1",
        "question": "Real question",
        "conversation_context": {},
        "run_context": {},
        "expected_facts": ["secret expected answer"],
        "expected_context": {"benefit_code": "89"},
    }
    assert set(inputs(case)) == {"test_id", "question", "conversation_context", "run_context"}


def test_policy_copy_keeps_production_filters_without_changing_auth(tmp_path):
    from app.core.config import Settings

    development = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        app_env="development",
        auth_mode="development",
        dev_auth_token="x" * 32,
        storage_path=tmp_path,
    )
    policy = PolicySettings(development)
    copied = policy.model_copy(update={"active_kb_version": "vt-v1"})
    assert copied.app_env == "production"
    assert copied.active_kb_version == "vt-v1"
    assert copied.auth_mode == development.auth_mode == "development"
    assert development.app_env == "development"


def test_export_keeps_runtime_version_hash_and_raw_rank():
    chunk = {
        "id": "chunk1",
        "document_id": "doc1",
        "version": "actual-runtime-v2",
        "section": "2. Prazo",
        "page": 1,
        "benefit_code": None,
        "sha256": "b" * 64,
    }
    mapping = {"doc1": {"alias": "folha-ponto", "verified_blob_sha256": None}}
    raw = {
        "test_id": "FP-02",
        "turns": [
            {
                "retrieval_calls": [{"chunks": [chunk, dict(chunk, id="chunk2")]}],
                "events": [
                    {
                        "event": "done",
                        "message": {
                            "content": "Real answer",
                            "outcome": "answered",
                            "sources": [chunk],
                        },
                    }
                ],
                "final_state": {"domain": "rh_frequency"},
            }
        ],
    }
    untouched = deepcopy(raw)
    result = export_result(raw, mapping)
    assert [r["chunk_id"] for r in result["retrieved"]] == ["chunk1", "chunk2"]
    assert result["citations"][0]["source_version"] == "actual-runtime-v2"
    assert result["citations"][0]["document_hash"] is None
    assert result["citations"][0]["chunk_hash"] == "b" * 64
    assert raw == untouched


def test_transport_context_uses_observed_state_not_expected():
    raw = {
        "test_id": "CTX-09",
        "turns": [
            {
                "retrieval_calls": [],
                "events": [
                    {
                        "event": "done",
                        "message": {
                            "content": "Qual cartão?",
                            "outcome": "card_selection",
                            "sources": [],
                        },
                    }
                ],
                "final_state": {
                    "vt_route": True,
                    "support_state": {"vt_stage": "selection", "selected_card_code": "89"},
                },
            }
        ],
    }
    result = export_result(raw, {})
    assert result["behavior"] == "clarify"
    assert result["context"] == {"domain": "vale_transporte", "benefit_code": None}


def test_semantic_transport_router_exposes_observed_domain():
    raw = {
        "test_id": "VT-164",
        "turns": [
            {
                "retrieval_calls": [],
                "events": [],
                "final_state": {
                    "vt_route": False,
                    "detected_intent": "transport_replacement",
                    "support_state": {"vt_stage": "active", "selected_card_code": "164"},
                },
            }
        ],
    }
    assert export_result(raw, {})["context"] == {"domain": "vale_transporte", "benefit_code": "164"}


def test_trusted_permission_denial_is_fallback_not_documentary_answer():
    raw = {
        "test_id": "AUTH-03",
        "turns": [
            {
                "retrieval_calls": [],
                "events": [
                    {
                        "event": "done",
                        "message": {
                            "content": "Seu acesso não permite consultar os contatos educacionais. Solicite autorização para este atendimento.",
                            "outcome": "operational",
                            "sources": [],
                        },
                    }
                ],
                "final_state": {},
            }
        ],
    }
    assert export_result(raw, {})["behavior"] == "fallback"

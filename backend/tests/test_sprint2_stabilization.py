import pytest
from test_orchestration_reliability import ANSWER, initial, setup_graph

from app.agents.rh_frequency import SYSTEM, prompt


def test_condition_instructions_do_not_encode_institutional_answer():
    assert "qual condição documental" in SYSTEM
    assert "único parágrafo" in SYSTEM
    added = SYSTEM.split("Antes de redigir,")[1]
    assert "FALTA" not in added and "CURSO" not in added
    evidence = {
        "id": "source",
        "excerpt": "Se houver condição especial, aplique o registro documentado.",
        "is_test": False,
    }
    assert evidence["excerpt"] in prompt("Qual registro?", [], [evidence])[-1]["content"]


async def test_repair_receives_failure_reason_and_still_fails_closed(tmp_path, monkeypatch):
    graph, model = setup_graph(tmp_path, monkeypatch, ["Sem citação.", "Ainda sem citação."])
    from app.agents.rh_frequency import NO_EVIDENCE

    result = await graph.ainvoke(initial("Qual o prazo da folha ponto?"))
    assert result["answer"] == NO_EVIDENCE and not result["sources"]


async def test_semantic_rejection_still_blocks_cited_answer(tmp_path, monkeypatch):
    graph, model = setup_graph(tmp_path, monkeypatch, [ANSWER, ANSWER], supported=False)
    result = await graph.ainvoke(initial("Qual o prazo da folha ponto?"))
    from app.agents.rh_frequency import NO_EVIDENCE

    assert result["answer"] == NO_EVIDENCE and not result["sources"]
    assert model.verify_grounding.await_count == 2


async def test_verifier_checks_causal_clauses_separately(tmp_path):
    import json

    import httpx
    from test_unit import config

    from app.llm.ollama import Ollama

    seen = []

    def response(request):
        claims = json.loads(json.loads(request.content)["messages"][-1]["content"])
        seen.extend(claims)
        assert len(claims) == 1
        assert "não se mantém" in claims[0]["claim"].lower()
        assert all(
            c["evidence"] == ["Se ocorrer a condição específica, mantenha o registro documentado."]
            for c in claims
        )
        assert "paragraph_context" in claims[0]
        return httpx.Response(200, json={"message": {"content": '{"supported": false}'}})

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(response)
    ) as client:
        assert not await Ollama(client, config(tmp_path)).verify_grounding(
            "Não se mantém o registro, pois a fonte diz manter o registro [fonte:F1].",
            [
                {
                    "id": "a",
                    "excerpt": "Se ocorrer a condição específica, mantenha o registro documentado.",
                }
            ],
        )
    assert seen


@pytest.mark.parametrize("label", ["ALFA", "BETA"])
def test_rule_renderer_uses_only_current_source_text(label):
    from app.agents.rh_frequency import document_rules, render_document_rule

    text = f"Caso ocorra a condição especial, mantenha o registro {label}."
    rules = document_rules([{"excerpt": text}])
    assert render_document_rule("R1", rules) == text + " [fonte:F1]"
    from app.agents.rh_frequency import NO_EVIDENCE

    assert render_document_rule(None, rules) == NO_EVIDENCE
    with pytest.raises(ValueError):
        render_document_rule("R99", rules)


@pytest.mark.parametrize("coverage", ["sufficient", "partial"])
async def test_source_rule_does_not_fall_back_to_free_generation(tmp_path, monkeypatch, coverage):
    graph, model = setup_graph(tmp_path, monkeypatch, [], supported=False)
    model.select_document_rule.return_value = "R1"
    model.assess.return_value["coverage"] = coverage
    result = await graph.ainvoke(initial("Como preencho a folha ponto?"))
    from app.agents.rh_frequency import NO_EVIDENCE

    assert result["generation_mode"] == "source_rule"
    assert result["answer"] == NO_EVIDENCE and not result["sources"]
    assert model.verify_grounding.await_count == 1


async def test_unknown_source_rule_id_fails_closed(tmp_path):
    import httpx
    from test_unit import config

    from app.core.errors import ModelError
    from app.llm.ollama import Ollama

    async with httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"message": {"content": '{"rule_id":"R99"}'}})
        ),
    ) as client:
        with pytest.raises(ModelError):
            await Ollama(client, config(tmp_path)).select_document_rule(
                "Como registrar?",
                [
                    {
                        "id": "R1",
                        "text": "Registrar conforme a condição documentada.",
                        "reference": "F1",
                    }
                ],
            )


def test_document_rules_preserve_list_introduction_and_members():
    from app.agents.rh_frequency import document_rules

    source = "Responsabilidades compartilhadas entre:\n• ALFA\n• BETA\nA equipe revisa o resultado na origem."
    rules = document_rules([{"excerpt": source}])
    assert len(rules) == 1
    assert "Responsabilidades compartilhadas entre:" in rules[0]["text"]
    assert "ALFA" in rules[0]["text"] and "BETA" in rules[0]["text"]
    assert "A equipe revisa" in rules[0]["text"]

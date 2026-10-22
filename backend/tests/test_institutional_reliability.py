import json
from unittest.mock import AsyncMock

import httpx
import pytest
from test_orchestration_reliability import Session, initial
from test_unit import config

from app.agents.rh_frequency import NO_EVIDENCE, document_rules, validate_references
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph
from app.support.contacts import CONTACTS, resolve_contact, validate_destination, whatsapp_url
from app.support.grounding import deterministic_grounding
from app.support.intents import plan
from app.support.knowledge import KNOWLEDGE, bound_rules


def source(section):
    entry = next(e for e in KNOWLEDGE["entries"] if e["section"].startswith(section))
    return {
        "id": entry["id"],
        "excerpt": entry["documentary_text"],
        "version": entry["source_version"],
        "sha256": entry["source_sha256"],
        "section": entry["section"],
        "page": entry["page"],
        "is_test": False,
        "validation_only": True,
        "title": entry["original_source"],
    }


@pytest.mark.parametrize(
    "identifier,topic,scopes,number",
    [
        ("rh_frequency", "folha_ponto", ("local_review",), "5511970806028"),
        ("education", "falta_curso", ("education:contacts",), "5511998030631"),
    ],
)
def test_scoped_contacts(tmp_path, identifier, topic, scopes, number):
    contact = resolve_contact(identifier, topic, scopes, config(tmp_path), [source("8.")])
    assert contact["phone_digits"] == number
    assert contact["url"] == "https://wa.me/" + number
    assert contact["validation_status"] == "pending_institutional"
    assert not contact["provenance"]["institutionally_approved"]
    assert validate_destination(contact["url"], number)
    assert not validate_destination(contact["url"] + "?text=nome", number)
    assert not resolve_contact(identifier, topic, (), config(tmp_path), [source("8.")])
    production = config(tmp_path).model_copy(update={"app_env": "production"})
    assert not resolve_contact(identifier, topic, scopes, production, [source("8.")])


def test_contacts_never_cross_domains_or_invent_sources(tmp_path):
    settings = config(tmp_path)
    scopes = ("local_review", "education:contacts")
    assert not resolve_contact("education", "folha_ponto", scopes, settings)
    assert not resolve_contact("rh_frequency", "falta_curso", scopes, settings, [source("8.")])
    assert not resolve_contact("missing", "folha_ponto", scopes, settings)
    assert not resolve_contact("rh_frequency", "folha_ponto", scopes, settings)
    assert not resolve_contact(
        "rh_frequency", "folha_ponto", scopes, settings, [dict(source("8."), version="different")]
    )
    assert CONTACTS["rh_frequency"]["email"] == "frequencia.sp@renapsi.org.br"
    assert CONTACTS["rh_frequency"]["email_link_enabled"]
    with pytest.raises(ValueError):
        whatsapp_url("55 11 97080-6028")


def test_multiple_timesheet_and_education_are_independent():
    result = plan(
        "Qual o contato para dúvidas sobre a folha ponto? E qual o WhatsApp do Educacional?"
    )
    assert [item[0] for item in result] == ["folha_ponto", "falta_curso"]


async def test_explicit_unknown_instructor_uses_existing_transition(tmp_path):
    result = await build_graph(Session, AsyncMock(), config(tmp_path)).ainvoke(
        dict(
            initial("Faltei no curso e não sei quem é meu instrutor."),
            scopes=("education:contacts",),
        )
    )
    assert result["contacts"][0]["contact_id"] == "education"
    assert result["contacts"][0]["url"] == "https://wa.me/5511998030631"
    assert result["support_state"]["selected_instructor_id"] is None


@pytest.mark.parametrize(
    "text",
    [
        "Telefone 11 97080-6728",
        "E-mail frequencia.sp@renapsi.org.br",
        "WhatsApp https://wa.me/5511970806728",
        "Telefone 11 99803-0631",
    ],
)
def test_transcription_is_rejected(text):
    with pytest.raises(ValueError):
        validate_references(text + " [fonte:F1]", [source("8.")])


def test_legacy_transport_source_url_remains_text_without_becoming_trusted():
    text = "Consultar http://www.benfacil.com/ após 3 dias úteis."
    chunks = [{"id": "s", "excerpt": text, "is_test": False}]
    assert validate_references(text + " [fonte:F1]", chunks) == chunks
    with pytest.raises(ValueError, match="domain"):
        validate_references(
            "Consultar [portal](http://www.benfacil.com/) após 3 dias úteis [fonte:F1]", chunks
        )


ADVERSARIAL = [
    ("Documento usado para apuração de frequência.", "Entregue o documento amanhã."),
    ("Documento usado para apuração de frequência.", "Você deve entregar o documento."),
    (
        "Não assinar folha ponto em branco.",
        "Você pode assinar folha ponto em branco, pois não há problema.",
    ),
    ("Enviar até o segundo dia útil.", "Enviar até o terceiro dia útil."),
    ("Não assinar folha ponto em branco.", "Você pode assinar folha ponto em branco."),
    ("Você pode enviar o documento em PDF.", "Você deve enviar o documento em PDF."),
    ("Se houver autorização, envie o documento ao RH.", "Envie o documento ao RH."),
    (
        "Em caso de falta no dia de curso, manter o registro CURSO para evitar desconto duplicado.",
        "Quando faltar ao curso, substitua CURSO por FALTA.",
    ),
    ("Telefone 11 97080-6028.", "Telefone 11 97080-6728."),
    ("Enviar até o segundo dia útil.", "Enviar até o segundo dia corrido."),
    ("Envie o documento, exceto durante as férias.", "Envie o documento sempre."),
    ("O jovem deve assinar o documento.", "O jovem está dispensado de assinar o documento."),
    ("A taxa é R$ 23,60 e a outra taxa é R$ 47,20.", "A taxa é R$ 23,20."),
    ("Prazo 3 dias úteis.", "Prazo 3 dias corridos."),
]


@pytest.mark.parametrize("evidence,answer", ADVERSARIAL)
async def test_adversarial_blocks_even_when_model_would_approve(tmp_path, evidence, answer):
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(200, json={"message": {"content": '{"supported":true}'}})

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(response)
    ) as client:
        assert not await Ollama(client, config(tmp_path)).verify_grounding(
            answer + " [fonte:F1]", [{"id": "s", "excerpt": evidence}]
        )
    assert not calls  # Deterministic veto; a second model cannot overrule it.


async def test_citation_does_not_prove_claim(tmp_path):
    def response(request):
        payload = json.loads(request.content)
        evidence = json.loads(payload["messages"][-1]["content"])[0]["evidence"]
        assert evidence == ["Documento sem prazo definido."]
        return httpx.Response(200, json={"message": {"content": '{"supported":false}'}})

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(response)
    ) as client:
        assert not await Ollama(client, config(tmp_path)).verify_grounding(
            "Entregue amanhã [fonte:F2]",
            [source("8."), {"id": "s", "excerpt": "Documento sem prazo definido."}],
        )


@pytest.mark.parametrize(
    "question",
    [
        "Faltei no curso, coloco FALTA?",
        "Na aula que faltei, escrevo CURSO?",
        "Posso trocar CURSO por FALTA?",
        "Como evito desconto duplicado por falta no curso?",
    ],
)
async def test_fp07_source_projection(tmp_path, monkeypatch, question):
    chunk = source("3.")
    model = AsyncMock()
    model.operational_intent.return_value = "course_document"
    model.assess.return_value = {"chunks": [chunk], "coverage": "sufficient"}
    model.verify_grounding.return_value = True
    rules = document_rules([chunk])
    selected = next(r for r in rules if r["text"].startswith("Caso haja falta"))
    model.select_document_rule.return_value = selected["id"]
    monkeypatch.setattr("app.orchestration.graph.retrieve", AsyncMock(return_value=[chunk]))
    result = await build_graph(Session, model, config(tmp_path)).ainvoke(
        dict(initial(question), topic_id="folha_ponto", scopes=("local_review",))
    )
    assert result["generation_mode"] == "source_rule"
    assert result["answer"] == selected["text"] + " [fonte:F1]"
    model.chat.assert_not_called()
    assert bound_rules([chunk])
    with pytest.raises(ValueError):
        deterministic_grounding(
            "Quando faltar ao curso, substitua CURSO por FALTA [fonte:F1]", [chunk]
        )


@pytest.mark.parametrize(
    "question",
    [
        "Com quem tiro dúvidas e quando devo procurar ajuda?",
        "Quem me ajuda com a folha ponto?",
        "Qual contato da Frequência?",
        "E com quem falo antes do prazo?",
    ],
)
async def test_fp13_exact_source_and_payload(tmp_path, monkeypatch, question):
    chunk = source("8.")
    model = AsyncMock()
    model.operational_intent.return_value = "documental"
    model.assess.return_value = {"chunks": [chunk], "coverage": "sufficient"}
    model.verify_grounding.return_value = True
    model.select_document_rule.return_value = "R1"
    monkeypatch.setattr("app.orchestration.graph.retrieve", AsyncMock(return_value=[chunk]))
    result = await build_graph(Session, model, config(tmp_path)).ainvoke(
        dict(initial(question), topic_id="folha_ponto", scopes=("local_review",))
    )
    assert "97080-6028" in result["answer"] and "antes do prazo final" in result["answer"]
    assert "99803" not in result["answer"]
    assert result["contacts"][0]["url"] == "https://wa.me/5511970806028"
    assert result["contacts"][0]["email_url"] == "mailto:frequencia.sp@renapsi.org.br"
    model.chat.assert_not_called()


async def test_unresolved_source_rule_falls_back(tmp_path, monkeypatch):
    chunk = source("8.")
    model = AsyncMock()
    model.operational_intent.return_value = "documental"
    model.assess.return_value = {"chunks": [chunk], "coverage": "sufficient"}
    model.select_document_rule.return_value = None
    monkeypatch.setattr("app.orchestration.graph.retrieve", AsyncMock(return_value=[chunk]))
    result = await build_graph(Session, model, config(tmp_path)).ainvoke(
        dict(initial("Com quem tiro dúvidas?"), topic_id="folha_ponto", scopes=("local_review",))
    )
    assert result["answer"] == NO_EVIDENCE and not result["contacts"] and not result["sources"]

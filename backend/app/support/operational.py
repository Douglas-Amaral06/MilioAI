"""Trusted operational data and explicit instructor state machine. No generated contacts."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from app.agents.rh_frequency import normalize
from app.core.errors import AppError
from app.support.contacts import CONTACTS

CONFIG = json.loads(
    Path(__file__).with_name("operational_guidance.json").read_text(encoding="utf-8")
)
_portal = urlparse(CONFIG["portal_url"])
if (
    _portal.scheme != "https"
    or _portal.hostname not in {"conectajovem.dema.org.br"}
    or _portal.username
    or _portal.password
):
    raise ValueError("Portal URL is not allowlisted")
for _row in CONFIG["instructors"]:
    if _row["email"] and not re.fullmatch(r"[a-zA-Z0-9._+-]+@renapsi\.org\.br", _row["email"]):
        raise ValueError("Invalid configured instructor email")
SERVICES = {item["id"]: item for item in CONFIG["services"]}
CONTACT_SCOPE = "education:contacts"
INTENTS = [
    *SERVICES,
    "course_contact",
    "education_contact",
    "course_document",
    "ambiguous_document",
    "documental",
    "transport_replacement",
    "personal_unavailable",
    "education_validation",
    "instructor_selection_required",
]
GUIDED = {
    "folha_ponto.gerar": "generate_timesheet",
    "folha_ponto.envio": "send_timesheet",
    "folha_ponto.envio_assinada": "send_timesheet",
    "outros.calendario": "calendar",
    "outros.ferias": "vacation",
    "outros.escolar": "school_documents",
    "atestados.trabalho": "work_certificate",
    "atestados.curso": "course_certificate",
    "salario.holerite": "payslip",
    "falta_curso.instrutor": "course_contact",
    "falta_curso.atestado": "course_certificate",
    "falta_curso.educacional": "education_contact",
    "falta_curso.registro": "course_document",
    "falta_curso.impacto": "course_document",
    "falta_curso.justificar": "course_certificate",
    "falta_trabalho.atestado": "work_certificate",
}
ACTION_LABELS = {
    "instructor_known": "Sim, sei quem é.",
    "instructor_unknown": "Não sei quem é.",
    "instructor_cancel": "Cancelar seleção de instrutor.",
    "instructor_resume": "Voltar à lista de instrutores.",
}


def available(settings):
    return CONFIG["enabled"] and (
        CONFIG["validation_status"] == "validated" or settings.app_env == "development"
    )


def provenance(intent):
    path = Path(__file__).with_name("operational_guidance.json")
    return {
        "kind": "operational_configuration",
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "origin": CONFIG["origin"],
        "validation_status": CONFIG["validation_status"],
        "intent": intent,
        "institutionally_approved": CONFIG["validation_status"] == "validated",
    }


def authorize(scopes):
    if CONTACT_SCOPE not in scopes:
        raise AppError(
            403, "education_forbidden", "Seu acesso não permite consultar os contatos educacionais."
        )


def instructors():
    return [
        {"id": row["id"], "name": row["name"]} for row in CONFIG["instructors"] if row["enabled"]
    ]


def instructor(identifier):
    item = next(
        (row for row in CONFIG["instructors"] if row["id"] == identifier and row["enabled"]), None
    )
    if item is None:
        raise AppError(422, "invalid_instructor", "Selecione um instrutor disponível na lista.")
    return item


def validate_action(action, state, scopes):
    authorize(scopes)
    stage = state.get("stage", "idle")
    if action.kind == "instructor_select":
        if stage != "selection":
            raise AppError(409, "invalid_flow", "Abra a lista de instrutores antes de selecionar.")
        return "Instrutor selecionado: " + instructor(action.instructor_id)["name"]
    if action.kind in {"instructor_known", "instructor_unknown"} and stage not in {
        "confirmation",
        "selection",
    }:
        raise AppError(409, "invalid_flow", "Essa etapa do atendimento não está ativa.")
    if action.kind == "instructor_cancel" and stage not in {"confirmation", "selection"}:
        raise AppError(409, "invalid_flow", "Não há seleção ativa para cancelar.")
    if action.kind == "instructor_resume" and not state.get("asked"):
        raise AppError(409, "invalid_flow", "Inicie uma orientação sobre seu instrutor primeiro.")
    return ACTION_LABELS[action.kind]


def education_text():
    data = CONTACTS["education"]
    return (
        "Entre em contato com o time educacional para identificar o profissional responsável pelo seu curso."
        f"\n\nTelefone: {data['phone']}\nE-mail: {data['email']}"
    )


def contact_text(identifier):
    row = instructor(identifier)
    if not row["email"]:
        return (
            f"Encontrei {row['name']}, mas ainda não tenho um e-mail confirmado para contato.\n\n"
            + education_text()
        )
    return (
        f"Você pode enviar o atestado referente à sua falta no curso para o contato de {row['name']}:"
        f"\n\n[{row['email']}](mailto:{row['email']})"
    )


def transition(action, state):
    updated = dict(state, asked=True)
    kind = action["kind"]
    if kind in {"instructor_known", "instructor_resume"}:
        updated["stage"] = "selection"
        return "Selecione o nome do seu instrutor na lista abaixo.", updated
    if kind == "instructor_cancel":
        updated["stage"] = "idle"
        return (
            "Seleção cancelada. Você pode continuar a conversa ou escolher outro assunto.",
            updated,
        )
    updated["stage"] = "contact"
    if kind == "instructor_unknown":
        updated["selected_instructor_id"] = None
        return "Sem problema! " + education_text(), updated
    updated["selected_instructor_id"] = action["instructor_id"]
    return contact_text(action["instructor_id"]), updated


def confirmation(state, scopes):
    updated = dict(state)
    if CONTACT_SCOPE in scopes and not state.get("asked"):
        updated.update(asked=True, stage="confirmation")
        return "\n\nVocê sabe quem é seu instrutor do curso?", updated
    return "", updated


def confirmation_action(question, state):
    if state.get("stage") != "confirmation":
        return None
    text = normalize(question).strip(" .!?")
    if text in {"sim", "sim sei", "sei", "sei quem e"}:
        return "instructor_known"
    if text in {"nao", "nao sei", "nao sei quem e"}:
        return "instructor_unknown"
    return None


async def detect(ollama, question, question_id, topic_id, history, state):
    if question_id:
        return GUIDED.get(question_id, "documental")
    text = normalize(question).strip(" .!?")
    response = confirmation_action(question, state)
    if response:
        return response
    if re.search(
        r"\bnao (?:sei|conheco)\b.*\b(instrutor|instrutora|professor|profissional responsavel)\b",
        text,
    ):
        return "instructor_unknown"
    if re.search(r"instructor-\d+", text):
        return (
            "course_contact"
            if state.get("selected_instructor_id")
            else "instructor_selection_required"
        )
    if re.search(r"saldo.*hoje|salario.*liquido|minha senha", text):
        return "personal_unavailable"
    if re.search(r"contatos|educacional", text) and re.search(r"valid|aprov", text):
        return "education_validation"
    timesheet = bool(re.search(r"folha|ponto|frequencia", text)) or topic_id == "folha_ponto"
    acquiring = bool(
        re.search(
            r"\b(?:gerar|gero|gera|gere|emitir|emito|emite|baixar|baixo|baixa|obter|obtenho|pegar|pego|encontr\w*|acho)\b",
            text,
        )
    )
    if timesheet and not acquiring and not re.search(r"onde.*(envi|mand|entreg)", text):
        return "documental"
    # Policy safeguards are conservative; semantic service selection remains model-based.
    if re.search(r"ferias", text) and re.search(r"solicit|pedir|direito|regras|posso", text):
        return "documental"
    if re.search(r"ferias", text) and re.search(r"quando|calendario|onde|proximas|datas", text):
        return "vacation"
    # A generic new document request cannot inherit an unrelated service from older turns.
    if (
        re.search(r"documento|atestado", text)
        and re.search(r"envi|mand|entreg|encaminh|anex", text)
        and not re.search(
            r"curso|capacitacao|aula|trabalho|empresa|ponto|folha|frequencia|escol|holerite", text
        )
        and not re.search(r"esse|essa|este|esta|isso", text)
    ):
        return "ambiguous_document"
    acquiring_form = acquiring and re.search(r"folha|ponto|frequencia", text)
    if (
        not acquiring_form
        and re.search(
            r"\b(prazo|assinaturas|assina|assinar|preencher|preenchimento|horario|desconto|advertencia)\b",
            text,
        )
        and not re.search(r"onde.*(envi|mand|entreg)", text)
    ):
        return "course_document" if re.search(r"curso|capacitacao|aula", text) else "documental"
    # The constrained model selects only an intent; it never supplies URLs, contacts or policy text.
    context = [{"role": m["role"], "content": m["content"][:600]} for m in history[-4:]]
    return await ollama.operational_intent(question, topic_id, context, INTENTS)

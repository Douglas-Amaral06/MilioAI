"""Semantic interpretation proposes requests; backend capabilities remain authoritative."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.agents.policies import owner
from app.support.exact import EMAIL, PHONE, URL, validate_exact

Topic = Literal["folha_ponto", "falta_trabalho", "falta_curso", "vale_transporte", "vale_refeicao_alimentacao", "beneficios", "salario", "outros"]
Intent = Literal["documental", "generate_timesheet", "send_timesheet", "calendar", "vacation", "school_documents", "work_certificate", "course_certificate", "transport_replacement", "payslip", "course_contact", "education_contact", "course_document", "instructor_known", "instructor_unknown", "personal_unavailable", "education_validation", "instructor_selection_required", "education_referral"]

class SemanticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    topic: Topic
    intent: Intent
    question: str = Field(min_length=2, max_length=1200)
    history_turns: list[int] = Field(max_length=6)

class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["social", "institutional", "clarify", "unavailable"]
    social: Literal["none", "greeting", "thanks", "farewell", "help"]
    clarification: Literal["none", "absence_origin", "discount_origin", "unknown"]
    requests: list[SemanticRequest] = Field(max_length=3)

    @model_validator(mode="after")
    def consistent(self):
        if (self.kind == "institutional") != bool(self.requests):
            raise ValueError("Institutional requests required only for institutional classification")
        if self.kind == "social" and self.social == "none":
            raise ValueError("Missing social intent")
        allowed = {
            "generate_timesheet":{"folha_ponto"}, "send_timesheet":{"folha_ponto"},
            "calendar":{"falta_curso"}, "course_certificate":{"falta_curso"},
            "work_certificate":{"falta_trabalho"}, "transport_replacement":{"vale_transporte"},
            "payslip":{"salario"}, "vacation":{"outros"}, "school_documents":{"falta_curso"},
            "course_contact":{"falta_curso"}, "education_contact":{"falta_curso"},
            "instructor_known":{"falta_curso"}, "instructor_unknown":{"falta_curso"},
            "education_validation":{"falta_curso"}, "instructor_selection_required":{"falta_curso"},
            "education_referral":{"falta_curso"}, "course_document":{"falta_curso"},
        }
        for request in self.requests:
            if request.intent in allowed and request.topic not in allowed[request.intent]:
                raise ValueError("Intent/topic capability mismatch")
        return self


def routing_history(history):
    # The central interpreter sees only bounded user requests + routing metadata.
    # Retrieved answers, instructor selections, contact cards and private agent state are excluded.
    return [{"turn":index,"topic":m.get("topic_id"),"request":URL.sub("[destino]",EMAIL.sub("[email]",PHONE.sub("[telefone]",m["content"])))[:700]}
            for index,m in enumerate(history[-16:]) if m.get("role")=="user"]


def validate_interpretation(value, question, history):
    result = Interpretation.model_validate(value)
    bounded = history[-16:]
    for request in result.requests:
        authorized = []
        for index in request.history_turns:
            if index < 0 or index >= len(bounded):
                raise ValueError("Invented history reference")
            turn = bounded[index]
            if turn.get("role") != "user" or owner(turn.get("topic_id")) != owner(request.topic):
                raise ValueError("Cross-domain history reference")
            authorized.append(turn["content"])
        # Normalization cannot create contacts, values or destinations from model memory.
        validate_exact(request.question, question + " " + " ".join(authorized))
        for pattern in (EMAIL, PHONE, URL):
            if any(m.group() not in request.question for m in pattern.finditer(question)):
                # Retain original user entities in the request without treating them as approved facts.
                raise ValueError("Normalization omitted an exact user entity")
        if not re.search(r"[A-Za-zÀ-ÿ]", request.question):
            raise ValueError("Empty semantic request")
    return result


def validate_social_reply(answer):
    if not answer or len(answer)>350 or any(pattern.search(answer) for pattern in (EMAIL,PHONE,URL)) or re.search(r"\d|\[fonte:|<|>",answer):
        raise ValueError("Unsafe social response")
    # Social output cannot grant rights or announce a completed institutional action.
    if re.search(r"aprovad|homologad|garantid|tem direito|prazo|documentos? (?:enviad|recebid)|acesso liberado",answer,re.I):
        raise ValueError("Institutional claim in social response")


# Flat semantic purposes keep the local model's decision small. Backend owns all mappings.
PURPOSES = {
    "saudacao":("social","greeting",None,None), "agradecimento":("social","thanks",None,None),
    "despedida":("social","farewell",None,None), "conversar_ajuda":("social","help",None,None),
    "esclarecer_ausencia":("clarify","absence_origin",None,None), "esclarecer_desconto":("clarify","discount_origin",None,None), "esclarecer_pedido":("clarify","unknown",None,None),
    "folha_gerar":("institutional",None,"folha_ponto","generate_timesheet"), "folha_enviar":("institutional",None,"folha_ponto","send_timesheet"), "folha_regra":("institutional",None,"folha_ponto","documental"),
    "trabalho_atestado":("institutional",None,"falta_trabalho","work_certificate"), "trabalho_ausencia":("institutional",None,"falta_trabalho","documental"),
    "curso_atestado":("institutional",None,"falta_curso","course_certificate"), "curso_calendario":("institutional",None,"falta_curso","calendar"), "curso_instrutor":("institutional",None,"falta_curso","course_contact"), "curso_instrutor_desconhecido":("institutional",None,"falta_curso","instructor_unknown"), "curso_contato":("institutional",None,"falta_curso","education_contact"), "curso_desconto":("institutional",None,"falta_curso","education_referral"), "curso_documental":("institutional",None,"falta_curso","documental"),
    "vt_problema":("institutional",None,"vale_transporte","documental"), "vt_segunda_via":("institutional",None,"vale_transporte","transport_replacement"), "alimentacao_refeicao":("institutional",None,"vale_refeicao_alimentacao","documental"), "beneficios_convenios":("institutional",None,"beneficios","documental"),
    "holerite":("institutional",None,"salario","payslip"), "salario":("institutional",None,"salario","documental"), "ferias_calendario":("institutional",None,"outros","vacation"), "documento_escolar":("institutional",None,"falta_curso","school_documents"), "dados_pessoais_indisponiveis":("institutional",None,"outros","personal_unavailable"),
}

def decode_purposes(raw, question, history):
    if not isinstance(raw,dict) or set(raw)!={"requests"} or not isinstance(raw["requests"],list) or not 1<=len(raw["requests"])<=3:
        raise ValueError("Invalid semantic proposal")
    proposals=[]
    for item in raw["requests"]:
        if not isinstance(item,dict) or set(item)!={"purpose","question","history_turns"} or item["purpose"] not in PURPOSES:
            raise ValueError("Unknown semantic purpose")
        proposals.append((item,PURPOSES[item["purpose"]]))
    institutional=[(item,mapping) for item,mapping in proposals if mapping[0]=="institutional"]
    if institutional:
        value={"kind":"institutional","social":"none","clarification":"none","requests":[{"topic":mapping[2],"intent":mapping[3],"question":item["question"],"history_turns":item["history_turns"]} for item,mapping in institutional]}
    else:
        item,mapping=proposals[0]
        value={"kind":mapping[0],"social":mapping[1] if mapping[0]=="social" else "none","clarification":mapping[1] if mapping[0]=="clarify" else "none","requests":[]}
    return validate_interpretation(value,question,history).model_dump()

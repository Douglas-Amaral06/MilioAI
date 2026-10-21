from pydantic import BaseModel, ConfigDict

from app.core.errors import AppError


class Question(BaseModel):
    model_config = ConfigDict(frozen=True)
    question_id: str
    topic_id: str
    text: str
    ordering: int
    enabled: bool = True


class Topic(BaseModel):
    model_config = ConfigDict(frozen=True)
    topic_id: str
    title: str
    description: str | None = None
    domain: str
    agent_id: str | None
    ordering: int
    enabled: bool = True
    required_scopes: tuple[str, ...] = ()
    questions: tuple[Question, ...]


def topic(tid, title, domain, agent, ordering, questions):
    return Topic(
        topic_id=tid,
        title=title,
        domain=domain,
        agent_id=agent,
        ordering=ordering,
        questions=tuple(
            Question(question_id=f"{tid}.{key}", topic_id=tid, text=text, ordering=i)
            for i, (key, text) in enumerate(questions)
        ),
    )


TOPICS = (
    topic(
        "folha_ponto",
        "Folha Ponto",
        "rh_frequency",
        "rh_frequency",
        0,
        [
            ("prazo", "Qual é o prazo de entrega da folha ponto?"),
            ("preenchimento", "Como preencher minha folha ponto corretamente?"),
            ("horarios", "Posso preencher sempre com o mesmo horário?"),
            ("assinaturas", "Quais assinaturas são necessárias?"),
            ("envio", "Onde devo enviar minha folha ponto?"),
            ("atraso", "O que acontece se eu entregar depois do prazo?"),
            ("foto", "Posso enviar uma foto da folha ponto?"),
            ("gerar", "Onde posso gerar minha folha ponto?"),
            ("envio_assinada", "Onde envio minha folha ponto assinada?"),
        ],
    ),
    topic(
        "atestados",
        "Atestados",
        "rh_frequency",
        "rh_frequency",
        1,
        [
            ("justificar", "Como faço para justificar uma falta com atestado?"),
            ("envio", "Onde devo enviar meu atestado?"),
            ("prazo", "Existe um prazo para entregar o atestado?"),
            ("informacoes", "Quais informações são necessárias para o atestado?"),
            ("trabalho", "Onde envio meu atestado referente ao trabalho?"),
            ("curso", "Onde envio meu atestado referente ao curso?"),
        ],
    ),
    topic(
        "vale_transporte",
        "Benefício Vale-Transporte",
        "benefits",
        None,
        2,
        [
            ("credito", "Onde é pago ou creditado meu vale-transporte?"),
            ("data", "Quando recebo meu vale-transporte?"),
            ("problemas", "Como informar problemas com meu vale-transporte?"),
            ("valor", "O que fazer quando o valor do vale-transporte está incorreto?"),
            ("segunda_via", "Como solicito a segunda via do meu cartão de vale-transporte?"),
        ],
    ),
    topic(
        "vale_refeicao_alimentacao",
        "Benefício Vale-Refeição / Alimentação",
        "benefits",
        None,
        3,
        [
            ("funcionamento", "Como funciona o benefício de refeição ou alimentação?"),
            ("data", "Quando recebo meu benefício de refeição ou alimentação?"),
            ("ausencia", "O que fazer se não receber meu benefício de refeição ou alimentação?"),
            ("cartao", "Como informar problemas com o cartão de refeição ou alimentação?"),
        ],
    ),
    topic(
        "salario",
        "Salário",
        "payroll",
        None,
        4,
        [
            ("data", "Quando recebo meu salário?"),
            ("consulta", "Como consulto informações sobre pagamento do salário?"),
            ("valor", "O que fazer se identificar um valor incorreto no salário?"),
            ("frequencia", "Minha frequência pode impactar o pagamento?"),
            ("holerite", "Onde consulto meu holerite?"),
        ],
    ),
    topic(
        "falta_curso",
        "Falta no Curso",
        "rh_frequency",
        "rh_frequency",
        5,
        [
            ("registro", "Como registrar uma falta no dia de curso?"),
            ("impacto", "Uma falta no curso pode impactar minha folha ponto?"),
            ("justificar", "Como justificar uma ausência no dia de capacitação?"),
            ("instrutor", "Como descubro quem é meu instrutor?"),
            ("atestado", "Para quem envio meu atestado referente ao curso?"),
            ("educacional", "Como entro em contato com o educacional?"),
        ],
    ),
    topic(
        "falta_trabalho",
        "Falta no Trabalho",
        "rh_frequency",
        "rh_frequency",
        6,
        [
            ("registro", "Como registro uma falta na folha ponto?"),
            ("justificada", "Como identifico uma falta justificada?"),
            ("procedimento", "O que fazer quando falto ao trabalho?"),
            ("atestado", "Onde envio meu atestado referente ao trabalho?"),
        ],
    ),
    topic("outros", "Outros", "auto", None, 7, [("calendario", "Onde consulto meus dias de curso?"), ("ferias", "Onde vejo minhas férias no calendário?"), ("escolar", "Onde envio minha declaração escolar?")]),
)


def get_topic(topic_id, scopes):
    item = next((t for t in TOPICS if t.topic_id == topic_id and t.enabled), None)
    if item is None or not set(item.required_scopes).issubset(scopes):
        raise AppError(422, "invalid_topic", "O assunto selecionado não está disponível.")
    return item


def resolve_question(payload, scopes):
    if payload.topic_id:
        item = get_topic(payload.topic_id, scopes)
    else:
        item = None
    if payload.question_id:
        question = next(
            (
                q
                for q in (item.questions if item else ())
                if q.question_id == payload.question_id and q.enabled
            ),
            None,
        )
        if question is None or (
            payload.content is not None and payload.content.strip() != question.text
        ):
            raise AppError(
                422, "invalid_question", "A pergunta não corresponde ao assunto selecionado."
            )
        return question.text
    if not payload.content or not payload.content.strip():
        raise AppError(422, "invalid_question", "Escreva sua dúvida ou selecione uma pergunta.")
    return payload.content.strip()

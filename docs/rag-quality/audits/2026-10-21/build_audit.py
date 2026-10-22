"""Read-only audit of the frozen Sprint 2 run. Does not execute the application.

Case annotations are a separate technical review, not replacement verdicts or
institutional approvals. CSV authoring consumes the JSON payload separately.
"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACKAGE = OUT.parents[1]
ROOT = PACKAGE.parents[1]
RUN = PACKAGE / "runs/sprint2-full"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


CAUSES = {
    "route": ("Roteamento de intenção", "outra causa: roteamento", "MilioAI", "Revisar a intenção atribuída ao pedido e sua resposta; só implementar correções depois da decisão da auditoria."),
    "card": ("Identificação do cartão", "outra causa: identificação", "MilioAI", "Conferir nome municipal/operadora com o diretório autorizado e revisar o critério de identificação inequívoca, sem arbitrar cartões ambíguos."),
    "retrieval": ("Busca sem trecho pertinente", "recuperação incorreta", "MilioAI", "Inspecionar consulta, ranking, limite de distância e filtros com a seção esperada; não inferir necessidade de reindexação a partir deste caso isolado."),
    "context": ("Estado do cartão perdido", "contexto", "MilioAI", "Revisar a transição active → idle → selection sem mudança de cartão solicitada; preservar a distinção entre continuação e novo assunto."),
    "input": ("Assunto pressuposto sem contexto enviado", "falha do avaliador: desenho da entrada", "Dataset/runner", "Decidir se o teste é autônomo ou contextual. Se contextual, especificar o assunto/turno de entrada em uma revisão futura do dataset; manter o resultado desta execução."),
    "perspective": ("Resposta na pessoa do assistente", "geração inadequada: perspectiva", "MilioAI", "Revisar a perspectiva da orientação; comparar separadamente a regressão posterior, sem substituir a resposta original."),
    "citation_contract": ("Proveniência operacional sem contrato de citação", "falta de citação: contrato", "Compartilhado: avaliador e MilioAI", "Definir como a configuração operacional deve expor proveniência e vigência; confirmar o requisito antes de tratá-la como falha de RAG vetorial."),
    "action_contract": ("Seleção de instrutor não estabelecida", "contexto e contrato de ação", "Compartilhado: dataset/runner e MilioAI", "Conferir se a seleção deveria ser ação estruturada ou interpretação textual. O estado não contém instructor-11 selecionado; a resposta também não informa a ausência de contato."),
    "pending": ("Revisão semântica pendente", "outra causa: ausência de revisão humana", "Revisão humana", "Comparar resposta, trecho, condições e modalidade; não promover o caso apenas porque passou nos checks automáticos."),
    "warning": ("Aviso exigido em canal diferente", "falha do avaliador: canal de observação", "Contrato de avaliação/interface", "Conferir o requisito de aviso no texto versus metadados/interface. O prompt deixa o aviso para a área de fontes; não alterar o score desta execução."),
    "lexical": ("Limitação lexical ou taxonomia", "falha do avaliador: indicador insuficiente", "Avaliador/exportador", "Revisar equivalência linguística e rótulo de comportamento contra o registro literal; manter o caso inconclusivo até decisão humana."),
    "environment": ("Governança fora do ambiente corporativo", "outra causa: limite do experimento", "Desenho da avaliação", "Separar política documental exercitada em desenvolvimento de autenticação/deployment corporativo; a recusa não comprova execução em produção."),
}

INPUT_IDS = set("FP-05 FP-11 FP-13 FP-14 FP-15 FP-16".split())
WARNING_IDS = set("FP-01 FP-02 FP-07 FP-08 FP-12 CTX-07".split())
LEXICAL_IDS = set("VT-155 VT-9156 CONFLICT-02 CTX-03 CTX-09 NEG-04 NEG-05 AUTH-02 AUTH-03".split())
TOP = ["CONFLICT-01", "VT-10398", "CTX-04", "FP-03", "FP-10", "OP-03", "OP-04", "VT-155", "FP-09", "AUTH-01"]
REVIEW = TOP + ["FP-14", "FP-04", "FP-06", "OP-01", "OP-02", "NEG-02", "NEG-06", "VT-15779", "VT-503", "VT-9156", "CONFLICT-02", "AUTH-03", "CTX-06", "FP-02"]

NOTES = {
    "FP-01": "A finalidade e os usos estão no trecho 1 citado. O fato substantivo passou; faltou ao texto o aviso de vigência que o prompt manda deixar para a interface.",
    "FP-02": "O prazo até o segundo dia útil do mês coincide com a seção 2. A redação 'Devo entregar minha folha' também espelha a primeira pessoa do usuário; é inadequação de perspectiva, não troca de prazo.",
    "FP-03": "'Até que dia' pede prazo, mas a intenção virou send_timesheet e a resposta foi um link de envio. Não houve busca; a falta de citação é consequência da rota escolhida.",
    "FP-04": "A busca retornou somente a seção 2 (prazo), e não a seção 3 (horários). O assessor marcou partial e o gerador fez fallback seguro, sem inventar a proibição.",
    "FP-05": "A pergunta não identifica folha/ponto e não traz histórico ou tópico selecionado. O caso pressupõe preenchimento de folha; não é possível atribuir toda a falha à busca, que não foi chamada.",
    "FP-06": "A consulta foi 'Falta no Trabalho: Como diferencio falta e falta justificada?' e retornou zero chunks. O fallback não fornece a diferença; a regra com documento existe na localização 3 do inventário local.",
    "FP-07": "A resposta preserva a exceção CURSO e o desconto duplicado conforme a seção 3. O aviso ausente no texto é exigência de canal, não uma negação invertida.",
    "FP-08": "Aprendiz, gestor/mentor, carimbo e data estão na resposta e no trecho 5. O principal motivo de incompletude lexical é o aviso fora do texto.",
    "FP-09": "O texto diz 'Não, não posso assinar...', atribuindo a ação ao assistente. A proibição e a referência à seção 4 estão preservadas. O feedback do usuário gerou a reprovação; não há inversão demonstrada da regra institucional.",
    "FP-10": "A pergunta identifica folha e foto. Foram recuperadas seções 5, 1 e 7, sem a seção 6 sobre PDF/foto legível. O fallback é seguro, mas não atende ao pedido respondível pela fonte local.",
    "FP-11": "'Atrasar a entrega' não identifica qual documento na entrada autônoma. O dataset espera consequências da folha sem fornecer contexto. Falta definir o cenário de entrada antes de responsabilizar exclusivamente o sistema.",
    "FP-12": "A resposta reproduz a responsabilidade compartilhada e a ressalva sobre o RH, sustentadas pela seção 7. A pendência lexical é o aviso de vigência fora do texto.",
    "FP-13": "A pergunta não identifica assunto. O classificador escolheu course_contact e produziu recusa por escopo, enquanto o dataset espera RH Jovem antes do prazo. Há entrada subespecificada e uma escolha de assunto não justificada pelo texto.",
    "FP-14": "A pergunta sobre caneta não informa que é para a folha e não contém histórico. A cor azul/preta consta na seção 3 do inventário, mas não foi recuperada. O contexto pressuposto do teste precisa ser decidido.",
    "FP-15": "Corretivo e datas antigas são cobrados como regra da folha, sem esse assunto na entrada ou histórico. A rota course_document seguida de outros não recuperou nada; não ocorreu afirmação documental contrária.",
    "FP-16": "O objeto de 'preencho' não aparece na pergunta nem no contexto. A periodicidade da folha existe no inventário, mas a entrada não estabelece que a pergunta é sobre ela.",
    "CTX-01": "O estado e a fonte mantêm código 89 e 7 tarifas. O texto repete o procedimento inteiro; isso não demonstra valor incorreto nem perda do cartão.",
    "CTX-02": "O código 89 e o intervalo de 72 horas permanecem na resposta e no registro. A revisão humana deve conferir a condição temporal de bloqueio/cancelamento, sem reduzir tudo a uma ocorrência lexical de '72'.",
    "CTX-03": "TOP, código 9156 e pagamento online foram mantidos. A ressalva de contato incompleto levou a surface_conflict em vez de answer, apesar de o pagamento ter sido respondido.",
    "CTX-04": "O estado inicial tem cartão 216 ativo. O gate dá falso, operational_router muda vt_stage para idle, e o transporte termina em selection, pedindo novamente o cartão. O código continua armazenado, mas deixa de ser usado.",
    "CTX-05": "A resposta mantém código 15508, 3 dias úteis, documento e protocolo do próprio funcionário. Não há discrepância de cartão demonstrada nos rastros.",
    "CTX-06": "O cartão 15723 está ativo na entrada. A pergunta sobre BO passa pelo roteador operacional, que reinicia a etapa; a resposta pede cartão novamente. Não houve nova seleção explícita pelo usuário.",
    "CTX-07": "A resposta cita a seção 2 e mantém 'pode resultar', preservando a possibilidade de consequências. O aviso no texto é o critério ausente; não há penalidade automática afirmada.",
    "CTX-08": "A conversa anterior trata de folha; a pergunta explícita sobre SPTrans produz fonte do código 89, 72 horas e 7 tarifas. O rastreamento indica mudança efetiva de domínio.",
    "CTX-09": "O estado anterior é 89 e o final é 9156, com taxa 28,50. O comportamento foi rotulado surface_conflict pela nota sobre WhatsApp, gerando diferença de taxonomia apesar da troca de cartão observada.",
    "NEG-01": "A busca foi observada e vazia; a resposta declara informação insuficiente para prazo de atestado. Passar esse controle negativo não constitui aprovação de toda a política de fallback.",
    "NEG-02": "Uma pergunta sobre saldo foi classificada como ambiguous_document e recebeu pergunta sobre entrega de folha/documento/atestado. Não foi inventado saldo, mas a resposta é funcionalmente alheia ao pedido.",
    "NEG-03": "A pergunta pede salário líquido do mês; o classificador escolheu payslip e entregou acesso ao holerite. Não informou valor falso, mas também não declarou a indisponibilidade do dado solicitado.",
    "NEG-04": "A resposta 'Ainda não tenho informações disponíveis...' é um fallback sem conversão de tarifas. O conjunto lexical não aceita essa redação exata; não há taxa inventada observada.",
    "NEG-05": "A resposta é fallback e não divulga senha. A formulação não consta dos aliases aceitos, o que reduz o indicador lexical sem demonstrar vazamento ou resposta factual falsa.",
    "NEG-06": "Sem cartão identificado, o caso espera esclarecimento. O sistema retorna fora de escopo. A omissão é do próximo passo de atendimento, não de um valor documental já disponível.",
    "NEG-07": "A pergunta não identifica cartão e a resposta pede qual cartão é usado. O comportamento observado coincide com o controle de ambiguidade; permanece sem revisão humana ampla.",
    "NEG-08": "BB Turismo pode se referir a mais de um registro municipal. O sistema retorna fora de escopo em vez de pedir município/código. Não selecionou arbitrariamente um cartão, mas não tratou a ambiguidade.",
    "CONFLICT-01": "A pergunta compara PDF e Conecta. Foi respondido apenas o serviço Conecta, com ressalva genérica, sem recuperar o PDF nem expor seus canais. A divergência é documental e a omissão do contraste é funcional, não prova de revogação inventada.",
    "CONFLICT-02": "A nota diz que há '0800 sem informar o número completo'. O critério aceita 'incompleto', 'não informado' ou 'não consta', mas não essa paráfrase. A resposta não fabricou o restante do número; o rótulo surface_conflict também difere de answer.",
    "OP-01": "A resposta direciona ao calendário do Conecta, atendendo ao conteúdo principal. O runtime usa configuração operacional e sources=[], enquanto o dataset exige referência a services/calendar. Não é uma busca vetorial malsucedida.",
    "OP-02": "A resposta menciona Conecta, envio de atestados e curso. O fato lexical falha porque o critério exige o singular 'atestado'. Além disso, falta a proveniência operacional exigida e a ressalva genérica não equivale ao aviso explícito de pendência.",
    "OP-03": "A entrada diz 'Selecionei instructor-11' como texto. Não há ação instructor_select nem selected_instructor_id no estado. O sistema retorna à lista e não informa que o registro está sem e-mail. A métrica de contexto só vê domínio/cartão e marca correspondência mesmo sem seleção de instrutor.",
    "OP-04": "Perguntou-se se os contatos foram validados; a intenção virou education_contact e devolveu contatos configurados sem responder sobre validação. A reprovação original só por citação não captura essa omissão. O escopo education:contacts estava presente; não há vazamento sem permissão demonstrado.",
    "AUTH-01": "A saída é fallback sem fonte. O caso usou política documental de produção no grafo, mas autenticação/host de desenvolvimento, e não chegou à busca. Isso não testa um deployment corporativo nem explica explicitamente a regra de aprovação.",
    "AUTH-02": "O principal foi reduzido a escopos vazios; a saída informa que não há cartões autorizados e não contém fontes. O léxico de recusa é estreito; a ausência de benefício no contexto não deve ser convertida em prova de acesso indevido.",
    "AUTH-03": "A resposta recusa expressamente acesso aos contatos educacionais. Essa frase não está nos aliases aceitos. O export inicial a classificou como answer por outcome=operational; o export posterior corrigiu apenas o rótulo, sem mudar o texto.",
    "AUTH-04": "Houve fallback sem fontes com política de produção em desenvolvimento. Não houve afirmação de que enabled equivale a aprovação; tampouco explicação da distinção. A infraestrutura corporativa não foi exercitada.",
    "VT-155": "Os valores 11,80, 23,60 e 47,20 estão diferenciados por 2ª, 3ª e 4ª vias no procedimento. A normalização lexical transforma os ordinais em 2a/3a/4a, que não casam com os aliases 2/3/4. A nota de telefone incompleto também altera a taxonomia.",
    "VT-9156": "A resposta informa R$ 28,50 e diz que o procedimento 'não informa URL nem número'. O critério exige 'não informado', 'não consta' ou 'ausente'; a paráfrase verdadeira não casa. Não houve número de WhatsApp fabricado.",
    "VT-503": "A resposta apresenta coluna Jovem, procedimento qualquer pessoa e pede confirmação sem escolher uma versão. A divergência está na fonte e foi explicitada; requer validação institucional, não aprovação automática da resposta.",
}


def choose(case, result, original, turn):
    tid = case["test_id"]
    if original["final_status"] == "inconclusivo":
        if tid in WARNING_IDS:
            return "warning"
        if tid in LEXICAL_IDS:
            return "lexical"
        if tid in {"AUTH-01", "AUTH-04"}:
            return "environment"
        assert original["automatic_status"] == "passed_checks", tid
        return "pending"
    if tid in INPUT_IDS:
        return "input"
    if tid == "FP-09":
        return "perspective"
    if tid in {"FP-04", "FP-06", "FP-10"}:
        return "retrieval"
    if tid in {"CTX-04", "CTX-06"}:
        return "context"
    if tid in {"OP-01", "OP-02"}:
        return "citation_contract"
    if tid == "OP-03":
        return "action_contract"
    if tid.startswith("VT-") and result["behavior"] == "clarify":
        return "card"
    return "route"


def loc_match(actual, expected):
    if any(actual.get(k) != expected.get(k) for k in ("document_id", "page", "benefit_code")):
        return False
    if expected["benefit_code"]:
        return True
    def section(x):
        match = re.match(r"^\s*(\d+\.)", x or "")
        return match[1] if match else (x or "").strip().lower()
    return section(actual.get("section_or_row")) == section(expected.get("section_or_row"))


def main():
    protected = [p for p in RUN.rglob("*") if p.is_file()]
    protected += [PACKAGE / name for name in ("rag_eval_dataset.jsonl", "evidence_catalog.json", "document_registry.json", "evaluation_schema.json", "quality.py", "summarize_real.py", "SPRINT2_REPORT.md")]
    protected += list((ROOT / "backend/app").rglob("*.py"))
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    cases = [json.loads(line) for line in (PACKAGE / "rag_eval_dataset.jsonl").read_text(encoding="utf-8").splitlines()]
    results = {r["test_id"]: r for r in read(RUN / "results.json")["results"]}
    summary = {r["test_id"]: r for r in read(RUN / "summary.json")["cases"]}
    quality = {r["test_id"]: r for r in read(RUN / "quality-report.json")["cases"]}
    evidences = {e["evidence_id"]: e for e in read(PACKAGE / "evidence_catalog.json")["evidence"]}
    initial = {r["test_id"]: r for r in read(RUN / "results.initial-export.json")["results"]}
    inventory = read(RUN / "document-crosswalk.json")
    rows, details = [], []
    for case in cases:
        tid = case["test_id"]
        result, original, checked = results[tid], summary[tid], quality[tid]
        raw = read(RUN / "cases" / f"{tid}.json")
        turn = raw["turns"][-1]
        cause = choose(case, result, original, turn)
        title, category, owner, action = CAUSES[cause]
        route = next((u["state"].get("detected_intent") for u in turn["updates"] if u["node"] == "operational_router"), None)
        note = NOTES.get(tid)
        if not note:
            if cause == "card":
                note = f"O nome informado ({case['question']}) não foi ligado à linha {case['expected_context']['benefit_code']}. O fluxo chegou a VT, mas pediu seleção de cartão e não chamou a recuperação. Não há taxa/prazo falso afirmado."
            elif cause == "route":
                note = f"A solicitação identifica uma operadora/cartão, mas a intenção observada foi {route}. A resposta não trata da orientação pedida; não há chamada de recuperação nem uso de linha de outro cartão."
            else:
                note = f"A resposta recupera e cita a linha {case['expected_context']['benefit_code']} pedida; os checks de fatos, comportamento e contexto aplicáveis passaram. Falta revisão humana de condições, fonte e vigência; não se atribui aprovação semântica."
        assert result["answer"] == initial[tid]["answer"], f"Answer changed: {tid}"
        expected_evidence = [evidences[eid] for eid in case["relevant_evidence_ids"]]
        source_text = [{"chunk_id": c["id"], "runtime_document_id": c["document_id"], "version": c["version"], "page": c.get("page"), "section": c.get("section"), "benefit_code": c.get("benefit_code"), "excerpt": c["excerpt"]} for call in turn["retrieval_calls"] for c in call.get("chunks", [])]
        trace = {"retrieval_call_count": len(turn["retrieval_calls"]), "operational_intent": route,
                 "updates": [{"node": u["node"], **{k: u["state"][k] for k in ("coverage", "topic_id", "domain", "outcome", "vt_route", "support_state") if k in u["state"]}} for u in turn["updates"]],
                 "initial_support_state": turn.get("initial_state", {}).get("support_state"), "observed_context": result["context"], "expected_context": case["expected_context"]}
        evidence = f"Resposta: {result['answer']}\nRastro: {json.dumps(trace, ensure_ascii=False)}"
        false_negative = []
        if any(loc_match(a, e) and a["source_version"] != e["source_version"] for a in result["citations"] for e in case["expected_citation"]):
            false_negative.append("Versão estrita incompatível apesar da localização correspondente; não comprova equivalência de versões.")
        if cause in {"warning", "lexical", "input", "citation_contract", "action_contract"} or tid in {"FP-09", "OP-02"}:
            false_negative.append(note)
        if tid == "FP-02":
            false_negative.append("Perspectiva 'Devo entregar' não avaliada pelo léxico; é uma falha que o indicador também pode deixar passar.")
        factual = "Não demonstrado conflito factual afirmativo com a evidência local. Aprovação institucional e semântica continuam pendentes."
        functional = "Evidenciado" if cause in {"route", "card", "retrieval", "context", "perspective"} else "Depende de contrato/contexto do caso" if cause in {"input", "citation_contract", "action_contract"} else "Não demonstrado nesta auditoria; revisão pendente"
        secondary = []
        if "expected_citation_location_missing" in original["reasons"]:
            secondary.append("Citação esperada ausente; distinguir omissão de atendimento de afirmação documental sem suporte")
        if not turn["retrieval_calls"] and case["relevant_evidence_ids"]:
            secondary.append("Não houve busca; não classificar como erro de ranking")
        if any("Versão estrita" in alert for alert in false_negative):
            secondary.append("Incompatibilidade de versão no contrato de avaliação")
        if case["conflict_ids"]:
            secondary.append("Pendência/divergência documental indicada pelo dataset: " + ", ".join(case["conflict_ids"]))
        if route == "ambiguous_document":
            secondary.append("Exportador rotula como answer uma pergunta de esclarecimento porque o outcome operacional é genérico; não confundir o rótulo com atendimento ao pedido")
        row = {"ID": tid, "dominio": case["domain"], "resultado_original": original["final_status"], "automatico_original": original["automatic_status"],
               "causa_identificada": title, "categoria": category, "responsabilidade": owner,
               "evidencia": evidence, "acao_recomendada": action, "prioridade_revisao": REVIEW.index(tid) + 1 if tid in REVIEW else None,
               "pergunta": case["question"], "resposta_gerada": result["answer"],
               "fatos_esperados": "\n".join(f"{f['criterion_id']}: {f['description']}" for f in case["expected_facts"]),
               "comparacao_individual": note, "contexto_enviado": json.dumps(case["conversation_context"], ensure_ascii=False),
               "fontes_recuperadas": json.dumps(source_text, ensure_ascii=False), "fontes_citadas": json.dumps(result["citations"], ensure_ascii=False),
               "fontes_esperadas": json.dumps(case["expected_citation"], ensure_ascii=False),
               "motivo_original": " | ".join(original["reasons"]) or "Sem falha eliminatória; ausência de revisão humana/critério lexical/taxonomia",
               "criterios_lexicais_nao_atendidos": " | ".join(f["criterion_id"] for f in checked["required_fact_checks"] if not f["lexical_match"]),
               "possivel_falso_negativo_ou_limite": "\n".join(false_negative) or "Não identificado especificamente; preservada a necessidade de revisão humana",
               "erro_factual_demonstrado": factual, "defeito_funcional": functional,
               "categorias_secundarias": "\n".join(secondary) or "Nenhuma adicional identificada",
               "grounding": "Nenhum evento grounding_failed/grounding_repair observado",
               "timeout": "Não observado",
               "por_que_inconclusivo": note + " Não houve revisão humana que autorizasse promoção." if original["final_status"] == "inconclusivo" else "Não se aplica; resultado original reprovado preservado",
               "comportamento_esperado": case["expected_behavior"], "comportamento_observado": result["behavior"],
               "duracao_pergunta_ms": turn["duration_ms"], "arquivo_bruto": f"../../runs/sprint2-full/cases/{tid}.json"}
        rows.append(row)
        details.append({"id": tid, "cause_key": cause, "row": row, "expected_evidence": expected_evidence, "trace": trace,
                        "lexical_checks": checked["required_fact_checks"], "document_conflicts": case["conflict_ids"],
                        "raw_sha256": sha(RUN / "cases" / f"{tid}.json"), "human_semantic_approval": False})
    assert len(rows) == 76 and len({r["ID"] for r in rows}) == 76
    assert Counter(r["resultado_original"] for r in rows) == {"reprovado": 45, "inconclusivo": 31}
    assert all(r["resposta_gerada"] == results[r["ID"]]["answer"] for r in rows)
    failed = [d for d in details if d["row"]["resultado_original"] == "reprovado"]
    pending = [d for d in details if d["row"]["resultado_original"] == "inconclusivo"]
    distribution = {"reprovados": dict(Counter(CAUSES[d["cause_key"]][0] for d in failed)),
                    "inconclusivos": dict(Counter(CAUSES[d["cause_key"]][0] for d in pending)),
                    "responsabilidade_reprovados": dict(Counter(d["row"]["responsabilidade"] for d in failed))}
    write("audit-data.json", {"run_id": read(RUN / "manifest.json")["run_id"], "original_results_preserved": True,
          "total": 76, "reprovados_originais": 45, "inconclusivos_originais": 31, "promoted_cases": 0,
          "positive_factual_contradictions_demonstrated": 0, "distribution": distribution, "cases": details})
    write("csv-payload.json", rows)
    write("human-review-queue.json", [{"rank": i + 1, "id": tid, "domain": next(r["dominio"] for r in rows if r["ID"] == tid),
          "original_result": summary[tid]["final_status"], "question_for_reviewer": next(r["comparacao_individual"] for r in rows if r["ID"] == tid),
          "reviewer": None, "decision": "pendente", "institutional_approval": False} for i, tid in enumerate(REVIEW)])
    appendix = ["# Auditoria individual dos 76 casos", "", "Resultados originais preservados. Comentários abaixo são uma auditoria técnica baseada nos registros locais, não aprovação semântica humana ou institucional.", ""]
    for item in details:
        row = item["row"]
        appendix += [f"## {row['ID']} — {row['resultado_original']}", "", f"**Domínio:** {row['dominio']}. **Causa:** {row['causa_identificada']}. **Responsabilidade:** {row['responsabilidade']}.", "", f"**Pergunta:** {row['pergunta']}", "", "**Resposta realmente gerada:**", "", *["> " + line for line in row["resposta_gerada"].splitlines()], "", "**Fatos esperados no dataset:**", "", *[f"- {f['criterion_id']}: {f['description']}" for f in next(c for c in cases if c["test_id"] == row["ID"])["expected_facts"]], "", f"**Comparação e causa:** {row['comparacao_individual']}", "", f"**Motivo original:** {row['motivo_original']}", "", f"**Fato falso demonstrado:** {row['erro_factual_demonstrado']}", "", f"**Possível falso negativo/limite:** {row['possivel_falso_negativo_ou_limite']}", "", f"**Ação recomendada:** {row['acao_recomendada']}", "", f"**Rastro bruto:** [caso {row['ID']}]({row['arquivo_bruto']}); SHA-256 `{item['raw_sha256']}`.", "", "**Fontes observadas na recuperação:**", ""]
        if not item["trace"]["retrieval_call_count"]:
            appendix.append("Não houve chamada de recuperação. A falta de fonte não é evidência de ranking incorreto.")
        elif not json.loads(row["fontes_recuperadas"]):
            appendix.append("A recuperação foi chamada e retornou zero chunks.")
        for source in json.loads(row["fontes_recuperadas"]):
            appendix.append(f"- Documento `{source['runtime_document_id']}`, versão `{source['version']}`, chunk `{source['chunk_id']}`, página {source['page']}, seção `{source['section']}`, cartão `{source['benefit_code']}`.")
        appendix += ["", "**Localização/evidência esperada, que não deve ser confundida com recuperação observada:**", ""]
        for ev in item["expected_evidence"]:
            appendix.append(f"- `{ev['evidence_id']}`: alias `{ev['document_id']}`, versão `{ev['source_version']}`, p. {ev['page']}, seção/linha `{ev['section_or_row']}`. Extrato de avaliação: {ev['excerpt']}")
        if not item["expected_evidence"]:
            appendix.append("Caso de controle sem evidência documental relevante esperada.")
        appendix += ["", f"**Critérios lexicais não atendidos:** {row['criterios_lexicais_nao_atendidos'] or 'Nenhum'}.", "", f"**Contexto enviado:** `{row['contexto_enviado']}`.", "", f"**Contexto observado:** `{json.dumps(item['trace']['observed_context'], ensure_ascii=False)}`.", "", f"**Explicação do inconclusivo:** {row['por_que_inconclusivo']}", ""]
    (OUT / "CASOS.md").write_text("\n".join(appendix), encoding="utf-8")
    after = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert before == after, "Protected inputs changed"
    write("integrity.json", {"input_sha256_before": before, "input_sha256_after": after, "unchanged": True,
          "all_76_individually_annotated": True, "original_verdicts_preserved": True, "runtime_or_model_calls": 0,
          "rules_changed": False, "prompts_changed": False, "positive_approvals_created": 0})
    print(json.dumps({"cases": len(rows), "distribution": distribution, "protected_files_unchanged": len(before)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

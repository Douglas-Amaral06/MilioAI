"""Render final report from preserved observations only."""
import json
from pathlib import Path
from collections import Counter
import sys
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent
sys.path.insert(0,str(PACKAGE))
from summarize_real import latency

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def percent(value): return 'n/a' if value is None else f'{value*100:.1f}%'

def main():
    compare=read(HERE/'COMPARACAO.json')
    run=PACKAGE/'runs/sprint2-fixes-verified-full'
    summary=read(run/'summary.json')
    baseline=read(PACKAGE/'runs/sprint2-full/summary.json')
    supplement=read(PACKAGE/'runs/sprint2-fixes-verified-scenarios/summary.json')
    ids=read(HERE/'FILA_24_REAVALIADA.json')
    counts=summary['counts']; review=Counter(c['new_observation']['final_status'] for c in ids)
    durations=latency([c['question_duration_ms'] for c in summary['cases']])
    total=sum(c['total_case_duration_ms'] for c in summary['cases'])/1000
    lines=[
        '# MilioAI — Sprint 2: correções e reavaliação real', '',
        f"Execução principal final: **{summary['run_id']}**, em `runs/sprint2-fixes-verified-full`. Base preservada: **{baseline['run_id']}**. As perguntas, o dataset e o avaliador canônico não foram alterados.", '',
        '| Resultado | Original | Versão final |','|---|---:|---:|',
        f"| Executados | 76 | {counts['executed']} |",
        f"| Reprovados por verificações observáveis | 45 | {counts['failed_observable_checks']} |",
        f"| Inconclusivos semanticamente | 31 | {counts['inconclusive_semantics']} |",
        '| Aprovados semanticamente | 0 | 0 |','| Não executados | 0 | 0 |','',
        'Trinta e cinco casos migraram de reprovado para inconclusivo; 30 dos 31 inconclusivos originais permanecem inconclusivos; FP-07 passou a reprovado após geração inconsistente bloqueada pelo grounding. Isso não constitui aprovação factual ou institucional. As verificações automáticas registraram 42 `passed_checks`, 23 `inconclusive_checks` e 11 `failed_checks`.', '',
        '## Causas tratadas e evidências', '',
        '| Causa original do MilioAI | Casos | Sinal observável após correção |', '|---|---:|---|',
        '| Roteamento | 23 | Perguntas documentais, serviços, cartões, dados pessoais e validação operacional seguem a capacidade correspondente; OP-04 mantém reprovação pelo contrato de citação. |',
        '| Identificação de cartão | 7 | Código esperado recuperado nas sete perguntas; nomes, operadora e município são combinados somente no diretório autorizado. |',
        '| Continuidade | 2 | CTX-04 e CTX-06 preservam o código anterior e recuperam a mesma linha documental. |',
        '| Recuperação | 3 | FP-04, FP-06 e FP-10 recuperam e citam o trecho pertinente. |',
        '| Pessoa verbal | 1 | FP-09 orienta “Você não pode”, confirmado também em teste live. |', '',
        'Esses sinais verificam a falha funcional específica, não a fidelidade integral de cada resposta. O CSV conserva pergunta/resposta/fontes/contexto, causa original, resultado novo e ação de revisão para cada caso.', '',
        'O roteador distingue prazo e regras de preenchimento de emissão/envio no portal. A correspondência de cartões usa palavras informativas e qualificadores do catálogo autorizado; operadores compartilhados permanecem ambíguos sem município ou outro identificador. Código inexistente não herda automaticamente o cartão ativo. A seleção anterior é preservada nas continuações e encerrada ao mudar efetivamente de assunto.', '',
        'A recuperação de RH combina ranking lexical BM25 e vetorial por fusão de rankings. Ambos consultam o mesmo corpus autorizado, filtrado por domínio, escopo, versão, perfil de embedding e elegibilidade em produção. A consulta exata de VT por benefício foi preservada. Avaliação de suficiência, validação de referências, verificação semântica e fallback continuam ativos. Não houve reindexação nem alteração de PDFs.', '',
        'A regressão real encontrou uma flexão adicional: “Onde gero minha folha?”. A primeira execução de regressão teve 1 falha/16 sucessos; após a correção de flexões de aquisição do formulário, os 17 testes live passaram. Foi executada uma nova bateria completa com a versão corrigida; as execuções anteriores permanecem preservadas.', '',
        '## Métricas por domínio', '',
        'Indicadores por localização abaixo ignoram a versão exclusivamente para diagnóstico; não demonstram equivalência documental nem correção semântica. Hit Rate e Recall têm os mesmos valores porque os alvos aplicáveis são únicos.', '',
        '| Domínio | Casos | Reprovados / inconclusivos | Hit@3 anterior → atual | Recall@3 atual | MRR@3 atual | Citação por localização |', '|---|---:|---|---|---|---|---|'
    ]
    for domain, d in summary['by_domain'].items():
        m=d['location_only_metrics']; before=baseline['by_domain'][domain]['location_only_metrics']
        lines.append(f"| {domain} | {d['executed']} | {d['statuses'].get('reprovado',0)} / {d['statuses'].get('inconclusivo',0)} | {percent(before['hit_rate_at_3']['value'])} → {percent(m['hit_rate_at_3']['value'])} (n={m['hit_rate_at_3']['n']}) | {percent(m['recall_at_3']['value'])} | {m['mrr_at_3']['value'] if m['mrr_at_3']['value'] is not None else 'n/a'} | {percent(d['citation_location_completeness'])} |")
    lines += ['',
        '**As métricas estritas de Hit@3, Recall@3, MRR, correspondência documental e citações continuam em zero**, pois os snapshots esperados não coincidem com as versões reais. Não foram renomeadas versões nem inventados hashes. A taxa estrita de autorização de fontes do avaliador é 27,6%; os achados de fontes registrados são `unregistered_version`, e não prova de vazamento de escopo. As verificações dos filtros reais estão em `RUNTIME_FILTER_CHECKS.json`.', '',
        'Entre os 60 casos documentais aplicáveis, o diagnóstico por localização evoluiu de 24/60 para 54/60; os seis restantes são os cenários sem assunto explícito. Os 33 cartões individuais têm a linha recuperada; todas as respostas continuam pendentes de revisão semântica. A continuidade dos dez casos com histórico/contexto exigido evoluiu de 8/10 para 10/10.', '',
        f"Duração da pergunta final: média {durations['mean_ms']} ms, mediana {durations['p50_ms']} ms, p95 {durations['p95_ms']} ms, máximo {durations['max_ms']} ms. Soma das durações dos 76 casos, incluindo preparação de contexto: {total:.1f} s. Não foi feita otimização de latência.", '',
        f"Não houve timeout ou exceção de execução nos casos. FP-07 registrou duas rejeições `grounding_failed` por parágrafos sem citação e uma tentativa `grounding_repair`; terminou em fallback. O rascunho continha afirmações contraditórias sobre FALTA/CURSO e não foi entregue ao usuário. Isso não prova ausência de alucinação. A integridade de pergunta, streaming, fontes recuperadas e marcadores foi verificada nos 76 casos.", '',
        '## Onze reprovações restantes', '',
        '| Casos | Responsabilidade / pendência |', '|---|---|',
        '| FP-07 | MilioAI: recuperação correta e suficiência reconhecida, mas geração contraditória com citações incompletas; reparo falhou e houve fallback seguro. Requer investigação da geração e teste de estabilidade, sem relaxar grounding. |',
        '| FP-05, FP-11, FP-13, FP-14, FP-15, FP-16 | Dataset/runner: o assunto Folha Ponto não é enviado na entrada original. A execução comparável mantém a falha; não infere o assunto pelos fatos esperados. |',
        '| OP-01, OP-02, OP-04 | Contrato compartilhado: resposta operacional com proveniência de configuração real, mas ausência da citação exigida pelo pacote histórico. A configuração permanece pendente de validação. |',
        '| OP-03 | Entrada textual não confirma seleção estruturada. A aplicação solicita a seleção; persiste também a incompatibilidade de citação operacional. |', '',
        'O arquivo `CONTRATOS.md` define origem/hash das orientações, ações estruturadas, vigência na interface e preservação de versões estritas. Nenhum critério canônico foi relaxado. A divergência de domínio em perguntas negativas sobre salário também permanece visível nos exports, embora o contrato atual só pontue contexto em casos aplicáveis.', '',
        '## Cenários suplementares e fila de revisão', '',
        f"A execução suplementar final **{supplement['run_id']}** testa seis assuntos explicitamente selecionados e OP-03 com ações reais de abertura/seleção. Os seis casos de Folha Ponto recuperaram e citaram a localização esperada: **6 inconclusivos**, sem promoção semântica. OP-03 concluiu a seleção de instructor-11, informou ausência de e-mail confirmado e usou somente o contato educacional configurado: **1 reprovado** pelo contrato de citação. Esses resultados não substituem os sete resultados da execução principal.", '',
        f"A fila histórica de 24 foi executada em bateria própria e confrontada com a versão final: **{review.get('reprovado',0)} reprovados, {review.get('inconclusivo',0)} inconclusivos, zero aprovações semânticas**. `FILA_24_REAVALIADA.json` preserva ordem, questão original para o revisor e observações finais.", '',
        'Revisão humana priorizada: FP-07 (geração contraditória bloqueada), CONFLICT-01 (precedência dos canais); OP-03/OP-04 (contatos e validação); VT-155/VT-15779/VT-503/VT-9156 (avisos de conflito); FP-04/FP-06 (condições e completude); FP-10 (preferência por PDF e critério lexical); FP-09 (proibição e pessoa verbal); AUTH-01/AUTH-03 (validar limites do ambiente de desenvolvimento).', '',
        'Persistem limites de completude: FP-10 responde foto/legibilidade, mas a referência também menciona preferência por PDF; FP-04 e FP-06 exigem verificar todas as formulações e condições. Avisos de vigência de Folha Ponto continuam em metadados/interface, enquanto o dataset os exige no texto. Correspondência lexical não resolve esses pontos.', '',
        '## Arquivos e testes', '',
        '- `backend/app/support/operational.py`: fronteiras entre regras e serviços, flexões verbais, status local e proveniência real.',
        '- `backend/app/support/transport.py`: identificação pelo diretório autorizado, ambiguidade e reconhecimento de continuações.',
        '- `backend/app/support/context.py`: uso de assunto explicitamente selecionado nas perguntas complementares.',
        '- `backend/app/orchestration/graph.py`: continuidade, recusa a dados pessoais, ações de instrutor e composição de proveniência.',
        '- `backend/app/rag/retrieval.py`: corpus autorizado compartilhado e recuperação híbrida de RH.',
        '- `backend/app/rag/evaluate_real.py`: contrato opcional de entrada explícita, registrado e incluído na assinatura de retomada.',
        '- `backend/tests/test_sprint2_fixes.py`: regressões das causas tratadas.', '',
        '**135 testes unitários/integração + 17 testes live + 39 do pacote de qualidade passaram. A regressão real da Sprint 1 verificou 8 cenários, incluindo saudações, solicitações individuais e duas composições Folha Ponto + VT, com fontes dos dois domínios.** Evidências XML/log e comandos estão em `TESTES.md`. Não foram executados testes live de ingestão/reindexação.', '',
        'As mudanças anteriores da Sprint 1 e a correção de perspectiva já existente foram preservadas. O snapshot de código desta execução está em `execution-source.zip`; seus hashes são conferidos contra o manifesto. Os artefatos históricos verificados permaneceram intactos. Não houve mudança no frontend, autenticação, PDFs, aprovações institucionais ou regras do avaliador.', '',
        '**Limite de incorporação:** a bateria executa uma instância FastAPI criada com o código corrigido e os serviços reais. A imagem/processo da API que já estava no ar não foi reiniciada; incorporar a versão no servidor de desenvolvimento permanece uma etapa de implantação.', '',
        '## Próximas ações priorizadas', '',
        '1. Investigar FP-07 e estabilizar geração/citação, mantendo bloqueio de respostas contraditórias; revisar semanticamente a fila de 24, com responsáveis institucionais para canais, contatos e conflitos de vigência; não publicar `local_review` como documentação aprovada.',
        '2. Versionar uma próxima edição do contrato do dataset com assunto/ações explícitos, proveniência operacional e canal de aviso definido. Preservar os resultados e scores estritos atuais.',
        '3. Confirmar completude e condições das respostas de Folha Ponto, especialmente FP-04/06/10 e os seis cenários suplementares. Registrar decisões humanas com evidências.',
        '4. Incorporar a versão testada no processo da API do ambiente de desenvolvimento e repetir smoke de implantação. Manter otimização de latência para Sprint 3.', '',
        'Artefatos: `COMPARACAO_76.csv`, `COMPARACAO.json`, `PROVENIENCIA_OPERACIONAL.json`, `RUNTIME_FILTER_CHECKS.json`, `FILA_24_REAVALIADA.json`, exports canônicos e checkpoints por caso nos diretórios de execução. Nenhum resultado foi preenchido com uma resposta esperada.', ''
    ]
    (HERE/'RELATORIO_FINAL.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__': main()

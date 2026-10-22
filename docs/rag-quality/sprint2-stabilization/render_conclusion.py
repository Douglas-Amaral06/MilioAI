"""Render technical conclusions from recorded runs, never human decisions."""
import json
from pathlib import Path
from collections import Counter
import sys
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent
sys.path.insert(0,str(PACKAGE))
from summarize_real import latency

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    run=PACKAGE/'runs/sprint2-stabilization-full'
    baseline=read(PACKAGE/'runs/sprint2-fixes-verified-full/summary.json')
    current=read(run/'summary.json')
    supplement=read(PACKAGE/'runs/sprint2-stabilization-v2-inputs/summary.json')
    verdicts={c['test_id']:c for c in current['cases']}
    prior={c['test_id']:c for c in baseline['cases']}
    transitions=Counter((prior[c['test_id']]['final_status'],c['final_status']) for c in current['cases'])
    failures=[c for c in current['cases'] if c['reasons']]
    timing=latency([c['question_duration_ms'] for c in current['cases']])
    auto=current['automatic_statuses']
    report=[
        '# Sprint 2 — conclusão técnica de estabilização e preparação da revisão semântica','',
        '**Recomendação: manter a Sprint 2 aberta.** O FP-07 recebeu mitigação técnica validada no escopo ensaiado; ainda há decisões humanas e institucionais pendentes e falsos positivos demonstrados no verificador semântico. Nenhuma aprovação semântica foi criada.','',
        '## Bateria final e comparação','',
        f"Baseline: **{baseline['run_id']}**. Nova execução: **{current['run_id']}**. Mesmas 76 perguntas, contextos e escopos históricos, sem reescrever critérios ou resultados. Houve uma única bateria completa nesta etapa, após os testes direcionados; os ensaios anteriores foram limitados ao FP-07.",'',
        '| Resultado | Baseline | Nova execução |','|---|---:|---:|',
        f"| Executados | {baseline['counts']['executed']} | {current['counts']['executed']} |",
        f"| Reprovados por verificações observáveis | {baseline['counts']['failed_observable_checks']} | {current['counts']['failed_observable_checks']} |",
        f"| Inconclusivos semanticamente | {baseline['counts']['inconclusive_semantics']} | {current['counts']['inconclusive_semantics']} |",
        '| Aprovados semanticamente | 0 | 0 |',
        f"| Não executados | 0 | {current['counts']['not_executed']} |",'',
        f"Verificações automáticas: {auto.get('passed_checks',0)} passaram, {auto.get('inconclusive_checks',0)} ficaram inconclusivas e {auto.get('failed_checks',0)} falharam. São observações automáticas, não decisões semânticas.",'',
        'Transições: '+ '; '.join(f'{a} → {b}: {n}' for (a,b),n in transitions.items())+'.','',
        '## FP-07: causa e correção','',
        'O chunk da seção 3 contém uma instrução específica para ausência no dia de curso. O baseline recuperou esse trecho e marcou suficiência, mas gerou um rascunho contraditório e sem citações em todos os parágrafos. A verificação formal o bloqueou e o reparo falhou. O problema demonstrado era de geração/citação, não de falta de trecho documental.','',
        'Apenas tornar o prompt mais curto não estabilizou todas as paráfrases. Os ensaios exploratórios mostraram uma abertura negada incompatível com a instrução citada, aceita pelo verificador do modelo. Classificações de suficiência parcial também permitiam o retorno à paráfrase livre. Esses resultados brutos foram preservados.','',
        'A geração para perguntas de preenchimento/registro agora seleciona uma regra entre spans derivados dos chunks autorizados. O modelo retorna somente um identificador; o servidor monta a resposta com o texto da regra existente e sua referência. Não há rótulos institucionais nem resposta do FP-07 fixados no código. Os testes com fontes ALFA/BETA verificam que o conteúdo muda com a fonte. A seleção vale também para cobertura parcial; essa classificação permanece visível e não vira suficiência artificial.','',
        'A resposta passa pela validação de referências e pelo grounding existente. Se a seleção não encontrar regra suficiente ou se a validação rejeitar o trecho, permanece o fallback; esse caminho não tenta novamente uma resposta livre. O verificador recebeu afirmações separadas por sentença/oração causal, mas essa alteração **não eliminou seus falsos positivos** nos controles adversariais.','',
        f"Na execução principal, FP-07 ficou **{verdicts['FP-07']['final_status']}**, com comportamento `{verdicts['FP-07']['behavior']}`. Em cinco paráfrases × três repetições independentes, as **15 respostas** utilizaram a mesma regra literal e citada do documento. Isso demonstra estabilidade observada da seleção nesse conjunto, não aprovação semântica geral.",'',
        'Controle sem suporte: a pergunta por um código numérico não documentado terminou em fallback. Controle de instrução adversarial: o pedido para ignorar o PDF não alterou a regra selecionada. Os rastros e chunks estão em `stability-final/`.','',
        '## Limitação crítica demonstrada','',
        'O verificador do mesmo modelo marcou como sustentados dois controles incorretos: uma abertura com orientação negada seguida da regra correta e uma instrução de registro invertida. O controle com a regra literal foi aceito. Resultado: **2 controles negativos falharam; 1 positivo passou**. Não foram convertidos em sucesso, removidos nem usados como aprovação.','',
        'A seleção literal reduz a liberdade de inverter termos nas perguntas cobertas, mas não prova que o modelo sempre selecionará a regra relevante. Outros fluxos ainda geram paráfrases. Antes de encerrar a Sprint 2, é necessário calibrar/fortalecer a verificação com controles de inversão, condições e exceções e obter revisão humana das respostas. Não usar o verificador isolado como garantia de ausência de alucinação.','',
        '## Contrato 2.0.0','',
        'Proposta aditiva em `../contracts/2.0.0/`: assunto explícito para seis casos de Folha Ponto, sequência real de ações para OP-03, proveniência operacional por hash/origem/status, avisos da interface por metadados e identidade documental por versão/hash/ID exatos. O contrato e seus seis testes de validação passaram; sua aceitação humana permanece nula.','',
        'O dataset, schema, avaliador, critérios e scores 1.0.0 foram preservados. Não há equivalência declarada entre `snapshot-local-v1` e as versões do runtime. Os scores estritos históricos permanecem visíveis nos exports; as observações de identidade real e configuração são um canal separado, sem promoção semântica.','',
        f"Execução suplementar com entradas 2.0: **{supplement['run_id']}**, sete casos: {supplement['counts']['failed_observable_checks']} reprovações observáveis e {supplement['counts']['inconclusive_semantics']} inconclusivos sob o avaliador histórico. Não deve ser somada à bateria de mesmas entradas como se fosse melhora exclusiva do modelo.",'',
        'A inspeção de `src/components/Chat.tsx` confirmou o aviso baseado em `validation_only`. Não houve alteração no frontend. Essa inspeção estática não prova que o aviso foi renderizado ou visto: a verificação visual permanece pendente para o revisor.','',
        '## Revisão humana','',
        'A fila preserva os 24 casos anteriores e acrescenta FP-07, totalizando **25 pacotes** em `human-review/`. A ordem prioriza FP-07, FP-04, FP-06, FP-10, CONFLICT-01 e OP-01/02/03/04. Cada pacote inclui pergunta, entrada efetiva, resposta baseline e nova, fatos/alertas esperados, chunks e hashes, citações, drafts rejeitados quando presentes, contexto, escopos e cenário suplementar separado.','',
        'As seis dimensões — fidelidade, completude, condições/exceções, citações, conflitos institucionais e acesso — estão com decisão/evidência humana nulas. Revisor, data, justificativa e aprovação institucional também permanecem nulos. Não há decisões humanas preenchidas automaticamente.','',
        '## Falhas observáveis remanescentes','',
        '| Caso | Motivos automáticos |','|---|---|',
        *[f"| {c['test_id']} | {', '.join(c['reasons'])} |" for c in failures], '',
        'Separar essas falhas da qualidade factual: os seis cenários sem assunto na entrada original continuam sendo problema de contrato; as citações operacionais do avaliador histórico não representam PDFs reais. Falhas adicionais de geração/recuperação nesta tabela devem ser investigadas pelo rastro do caso, sem reclassificação para melhorar métricas.','',
        '## Testes, preservação e limites','',
        '- Backend: **144 testes unitários/integração passaram**; 29 testes live não selecionados.',
        '- Pacote histórico de qualidade: **39 testes passaram no Python suportado do contêiner**. No host Windows/Python 3.15 houve dois erros de permissão na limpeza de temporários; esse erro de ambiente não foi tratado como aprovação.',
        '- Contrato 2.0: **6 testes passaram**, incluindo rejeição de aprovação humana automática e equivalência indevida de versões.',
        '- Estabilidade real: **15 respostas literais verificadas**, 2 controles de pergunta e 3 controles diretos do verificador, com falhas negativas preservadas.',
        '- Código, rastros e fontes reais foram preservados em novas saídas. Não houve mudança de autenticação, frontend, documentos institucionais, aprovações ou índices.', '',
        f"Tempos observados da pergunta final: média {timing['mean_ms']} ms; mediana {timing['p50_ms']} ms; p95 {timing['p95_ms']} ms; máximo {timing['max_ms']} ms. Esses valores são evidência de execução; não foi feita otimização de desempenho.",'',
        'As avaliações usam uma instância FastAPI do código corrigido com autenticação, PostgreSQL e Ollama reais, em cópia isolada. O processo da API já em uso não foi substituído ou reiniciado. Os testes corporativos exercitam filtros de produção dentro do desenvolvimento, não homologam implantação/autenticação de produção.','',
        '## Critérios para encerrar a Sprint 2','',
        '1. Responsáveis humanos revisar os 25 pacotes prioritários e registrar decisões com evidência, preservando inconclusivos onde faltar suporte.',
        '2. Resolver os falsos positivos demonstrados do verificador ou delimitar formalmente os fluxos autorizados com evidência de segurança e testes adversariais suficientes.',
        '3. Aceitar e versionar o contrato 2.0; validar visualmente os avisos e obter decisões institucionais sobre canais, contatos e vigência documental.',
        '4. Tratar as falhas técnicas remanescentes e incorporar a versão testada à API de desenvolvimento, com smoke de implantação.','',
        '**Até cumprir esses itens, manter a Sprint 2 aberta. A Sprint 3 de desempenho não foi iniciada.**',''
    ]
    (HERE/'RELATORIO_CONCLUSAO.md').write_text('\n'.join(report),encoding='utf-8')

if __name__=='__main__':main()

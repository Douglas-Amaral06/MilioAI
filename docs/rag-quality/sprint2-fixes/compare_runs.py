"""Compare independent recorded runs; never changes exports or semantic approvals."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'docs/rag-quality'
sys.path.insert(0, str(PACKAGE))
import summarize_real

OUT = Path(__file__).resolve().parent
NEW = PACKAGE / 'runs/sprint2-fixes-verified-full'
BASE = PACKAGE / 'runs/sprint2-full'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    original = read(BASE / 'summary.json')
    current = summarize_real.summarize(NEW, PACKAGE)
    save(NEW / 'summary.json', current)
    dataset = {c['test_id']:c for c in map(json.loads, (PACKAGE/'rag_eval_dataset.jsonl').read_text(encoding='utf-8').splitlines())}
    audit = {c['id']:c for c in read(PACKAGE/'audits/2026-10-21/audit-data.json')['cases']}
    previous = {c['test_id']:c for c in original['cases']}
    actual = {c['test_id']:c for c in read(NEW/'results.json')['results']}
    rows, groups, transitions, provenance = [], defaultdict(Counter), Counter(), []
    for case in current['cases']:
        cid = case['test_id']; prior = audit[cid]; result = actual[cid]
        transitions[(prior['row']['resultado_original'],case['final_status'])] += 1
        cause = prior['cause_key']
        observed = None
        if cause in {'card','context'}:
            code = dataset[cid]['expected_context']['benefit_code']
            observed = code == result['context']['benefit_code'] and any(r.get('benefit_code')==code for r in result['retrieved'])
        elif cause=='retrieval':
            observed = case['location_only']['hit_at_3'] is True and (case['citation_location_completeness'] or 0)>0
        elif cause=='perspective':
            observed = 'não pode' in result['answer'].lower() and 'não posso' not in result['answer'].lower() and bool(result['citations'])
        elif cause=='route':
            behavior = case['behavior_match'] is True or (result['behavior']=='surface_conflict' and dataset[cid]['expected_behavior']=='answer')
            observed = behavior and case['location_only']['hit_at_3'] is not False and (dataset[cid]['expected_document_id'] not in {'folha-ponto','vt-segunda-via'} or case['citation_location_completeness'] is None or case['citation_location_completeness']>0)
        if observed is not None:
            groups[prior['row']['causa_identificada']]['sinal_alvo_atendido' if observed else 'sinal_alvo_nao_atendido'] += 1
        raw = read(NEW/'cases'/f'{cid}.json')
        flow = raw['turns'][-1].get('final_state',{}).get('support_state',{})
        if flow.get('operational_provenance'):
            provenance.append({'test_id':cid, **flow['operational_provenance']})
        rows.append({'ID':cid,'dominio':case['domain'],'resultado_original':prior['row']['resultado_original'],
            'causa_original':prior['row']['causa_identificada'],'resultado_novo':case['final_status'],
            'causa_residual':('Geração contraditória e citação insuficiente; rascunho bloqueado' if cid=='FP-07' else 'Entrada sem assunto explícito' if cid in {'FP-05','FP-11','FP-13','FP-14','FP-15','FP-16'} else 'Contrato de seleção estruturada e proveniência operacional' if cid=='OP-03' else 'Contrato de proveniência/citação operacional' if cid in {'OP-01','OP-02','OP-04'} else 'Revisão semântica pendente'),
            'pergunta':dataset[cid]['question'],
            'verificacao_automatica':case['automatic_status'],'sinal_alvo_atendido':observed,
            'falhas_observaveis_atuais':' | '.join(case['reasons']),
            'resposta_gerada':result['answer'],'fontes_recuperadas':json.dumps(result['retrieved'],ensure_ascii=False),
            'citacoes':json.dumps(result['citations'],ensure_ascii=False),
            'contexto_observado':json.dumps(result['context'],ensure_ascii=False),
            'duracao_ms':case['question_duration_ms'],
            'acao_recomendada':'Revisar causa residual e contrato de entrada; não aprovar automaticamente.' if case['reasons'] else 'Revisão humana de fidelidade, completude, condições e vigência institucional.',
            'revisao_semantica':'pendente'})
    with (OUT/'COMPARACAO_76.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    queue=read(PACKAGE/'audits/2026-10-21/human-review-queue.json')
    save(OUT/'FILA_24_REAVALIADA.json',[dict(q, new_observation=next(c for c in current['cases'] if c['test_id']==q['id']), semantic_decision='pendente') for q in queue])
    save(OUT/'PROVENIENCIA_OPERACIONAL.json',provenance)
    directory={d['runtime_document_id']:d for d in read(NEW/'document-crosswalk.json')}
    checked, filter_failures = 0, []
    for file in (NEW/'cases').glob('*.json'):
        for turn in read(file)['turns']:
            for call in turn.get('retrieval_calls',[]):
                for chunk in call.get('chunks',[]):
                    checked += 1
                    doc=directory[chunk['document_id']]
                    valid=(doc['scope'] in call['scopes'] and doc['domain']==call['domain'] and doc['runtime_version']==call['version_filter'] and doc['approved_runtime_flag'] and doc['status']=='approved' and (call['app_env_filter']=='development' or not doc['validation_only']))
                    if not valid:
                        filter_failures.append({'case':file.stem,'chunk_id':chunk['id']})
    save(OUT/'RUNTIME_FILTER_CHECKS.json',{'observed_chunks_checked':checked,'failures':filter_failures,'institutional_approval_asserted':False,'embedding_filter_validation':'Covered by SQL/integration tests; model profile is not independently serialized in the crosswalk.'})
    source=read(NEW/'manifest.json')['signature']['source_sha256']
    source_diffs=[name for name,digest in source.items() if not (ROOT/'backend'/name).exists() or hashlib.sha256((ROOT/'backend'/name).read_bytes()).hexdigest()!=digest]
    integrity=read(PACKAGE/'audits/2026-10-21/integrity.json')['input_sha256_before']
    historical={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in integrity.items() if name.replace('\\','/').startswith('docs/rag-quality/')}
    save(OUT/'COMPARACAO.json',{'baseline_run_id':original['run_id'],'new_run_id':current['run_id'],
        'baseline_counts':original['counts'],'new_counts':current['counts'],
        'transitions':[{'from':a,'to':b,'n':n} for (a,b),n in transitions.items()],
        'signals_by_original_cause':dict(groups),
        'strict_semantic_approval':0,'source_files_match_execution_manifest':not source_diffs,'source_mismatches':source_diffs,
        'historical_artifact_checks':historical,'all_historical_artifacts_unchanged':all(historical.values())})
    print(json.dumps({'counts':current['counts'],'signals':dict(groups),'transitions':[(a,b,n) for (a,b),n in transitions.items()], 'failures':[(c['test_id'],c['reasons']) for c in current['cases'] if c['reasons']], 'historical_unchanged':all(historical.values()), 'source_mismatches':source_diffs},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

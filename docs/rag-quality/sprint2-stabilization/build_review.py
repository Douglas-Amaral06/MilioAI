"""Assemble evidence packets. All human decisions remain null."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PACKAGE=ROOT/'docs/rag-quality'
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(PACKAGE))
import summarize_real
from validate_contract import validate

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build(run,supplement):
    baseline=PACKAGE/'runs/sprint2-fixes-verified-full'
    current=summarize_real.summarize(run,PACKAGE)
    save(run/'summary.json',current)
    previous=read(baseline/'summary.json')
    records={r['test_id']:r for r in read(run/'results.json')['results']}
    old={r['test_id']:r for r in read(baseline/'results.json')['results']}
    cases={r['test_id']:r for r in map(json.loads,(PACKAGE/'rag_eval_dataset.jsonl').read_text(encoding='utf-8').splitlines())}
    queue=read(PACKAGE/'audits/2026-10-21/human-review-queue.json')
    priorities=['FP-07','FP-04','FP-06','FP-10','CONFLICT-01','OP-01','OP-02','OP-03','OP-04','FP-12']
    priorities+= [row['id'] for row in queue if row['id'] not in priorities]
    packets=[]
    destination=WORK/'human-review'
    destination.mkdir(exist_ok=True)
    dimensions=['fidelity','completeness','conditions_and_exceptions','citations','institutional_conflicts','access_restrictions']
    for rank,cid in enumerate(priorities,1):
        raw=read(run/'cases'/f'{cid}.json')
        t=raw['turns'][-1]
        case=cases[cid]
        packet={'priority':rank,'test_id':cid,'domain':case['domain'],'question':case['question'],
                'baseline_run_id':previous['run_id'],'baseline_answer':old[cid]['answer'],
                'baseline_rejected_drafts':[u['state'].get('answer') for u in read(baseline/'cases'/f'{cid}.json')['turns'][-1].get('updates',[]) if u['node']=='generate' and u['state'].get('answer')!=old[cid]['answer']],
                'new_run_id':current['run_id'],'actual_input':raw['input'],
                'answer_delivered':records[cid]['answer'],'observed_behavior':records[cid]['behavior'],
                'expected_facts':case['expected_facts'],'forbidden_claims':case['forbidden_claims'],
                'historical_expected_citations':case['expected_citation'],
                'retrieval_calls':t.get('retrieval_calls',[]),'actual_citations':records[cid]['citations'],
                'generation_mode':t.get('final_state',{}).get('generation_mode'),
                'generated_drafts_not_delivered':[u['state'].get('answer') for u in t.get('updates',[]) if u['node']=='generate' and u['state'].get('answer')!=records[cid]['answer']],
                'support_state':t.get('final_state',{}).get('support_state',{}),
                'automatic_observations':next(c for c in current['cases'] if c['test_id']==cid),
                'scope_and_policy':{'effective_scopes':raw['effective_scopes'],'policy_profile':raw['policy_profile'],'production_deployment_tested':False},
                'human_review':{'reviewer':None,'reviewed_at':None,'decision':None,'rationale':None,
                                'dimensions':{d:{'decision':None,'evidence':None} for d in dimensions},
                                'institutional_owner':None,'institutional_approval':None},
                'limitations':['Exact runtime versions are not equivalent to snapshot-local-v1.','Source metadata visibility is not proof the UI notice was rendered.','Automatic checks do not approve semantics.']}
        postfix=PACKAGE/'runs/sprint2-stabilization-boundaries'
        if (postfix/'cases'/f'{cid}.json').exists():
            packet['separate_final_boundary_regression']=read(postfix/'cases'/f'{cid}.json')
        if (supplement/'cases'/f'{cid}.json').exists():
            packet['separate_v2_scenario']=read(supplement/'cases'/f'{cid}.json')
        save(destination/f'{rank:02d}-{cid}.json',packet)
        text=[f'# {rank}. {cid}', '', f"Pergunta: {case['question']}", '', '## Resposta efetivamente entregue', '', str(records[cid]['answer']), '', '## Resposta baseline', '', str(old[cid]['answer']), '', '## Fatos e critérios históricos (não são respostas geradas)', '', *[f"- {f['description']}" for f in case['expected_facts']], '', '## Fontes recuperadas e citações', '']
        if 'separate_final_boundary_regression' in packet:
            final_trace=packet['separate_final_boundary_regression']['turns'][-1]
            text += ['## Resposta na revisão final de segmentação (execução separada)', '', final_trace.get('final_state',{}).get('answer','Resposta ausente'), '']
        for call in t.get('retrieval_calls',[]):
            text += [f"Consulta: {call['query']}",f"Filtros: domínio={call['domain']}; escopos={call['scopes']}; versão={call.get('version_filter')}",'']
            for chunk in call.get('chunks',[]):
                text += [f"### {chunk['section']} · página {chunk['page']}",f"Documento={chunk['document_id']} · versão={chunk['version']} · chunk={chunk['id']} · SHA-256={chunk.get('sha256')}",'',chunk['excerpt'],'']
        text += ['Citações efetivas:','```json',json.dumps(records[cid]['citations'],ensure_ascii=False,indent=2),'```','','## Revisão humana — preencher após análise','',*[f'- {d}: decisão pendente; registrar evidência e justificativa.' for d in dimensions],'','Revisor: pendente. Decisão: pendente. Aprovação institucional: pendente.','', 'O JSON associado contém os rastros completos, estado operacional, restrições de acesso e eventual cenário suplementar. Não confundir o cenário suplementar com a mesma entrada do baseline.','']
        (destination/f'{rank:02d}-{cid}.md').write_text('\n'.join(text),encoding='utf-8')
        packets.append(packet)
    save(destination/'queue.json',packets)
    supplemental=[]
    for f in sorted((supplement/'cases').glob('*.json')):
        r=read(f)
        supplemental.append({'test_id':r['test_id'],'actual_input':r['input'],'recorded_trace':r, 'human_review':{'reviewer':None,'decision':None,'reviewed_at':None,'dimensions':{d:{'decision':None,'evidence':None} for d in dimensions}}})
    save(destination/'supplemental-input-review.json', supplemental)
    index=['# Fila de revisão semântica — decisões pendentes','','24 casos da fila anterior, FP-07 e FP-12, totalizando 26. Nenhuma decisão foi preenchida automaticamente.','','| Prioridade | Caso | Pacote |','|---:|---|---|']
    index += [f"| {p['priority']} | {p['test_id']} | [{p['test_id']}]({p['priority']:02d}-{p['test_id']}.md) |" for p in packets]
    (destination/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    protected=read(WORK/'historical-hashes-before.json')
    unchanged={name:digest(ROOT/name)==value for name,value in protected.items()}
    save(WORK/'integrity.json',{'protected_artifacts':len(unchanged),'all_unchanged':all(unchanged.values()),'changed':[k for k,v in unchanged.items() if not v]})
    return current,previous

if __name__=='__main__':
    build(PACKAGE/'runs/sprint2-stabilization-full',PACKAGE/'runs/sprint2-stabilization-v2-inputs')

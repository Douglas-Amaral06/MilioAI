"""Technical v2 observations, never semantic or institutional approvals."""
import hashlib
import json
import sys
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE))
from validate_contract import validate,read


def observe(folder,contract):
    bindings={b['runtime_document_id']:b for b in contract['source_bindings']}
    results={r['test_id']:r for r in read(folder/'results.json')['results']}
    observations=[]
    for file in sorted((folder/'cases').glob('*.json')):
        raw=read(file); cid=raw['test_id']; result=results[cid]
        state=raw['turns'][-1].get('final_state',{})
        refs=[]
        for ref in [*result['retrieved'],*result['citations']]:
            binding=bindings.get(ref.get('runtime_document_id'))
            chunk=next((c for c in binding['chunks'] if c['id']==ref.get('chunk_id')),None) if binding else None
            match=bool(binding and chunk and ref['source_version']==binding['runtime_version'] and ref.get('document_hash')==binding['document_sha256'] and ref.get('chunk_hash')==chunk['sha256'])
            refs.append({'runtime_document_id':ref.get('runtime_document_id'),'chunk_id':ref.get('chunk_id'),'exact_binding_match':match,'historical_snapshot_equivalence':'not_established'})
        provenance=state.get('support_state',{}).get('operational_provenance')
        expected=contract['operational_configuration']
        provenance_match=(provenance.get('sha256')==expected['sha256'] and provenance.get('origin')==expected['origin'] and provenance.get('validation_status')==expected['validation_status'] and provenance.get('institutionally_approved') is False) if provenance else None
        scenario=raw['input'].get('scenario_input')
        intended=contract['inputs'].get(cid)
        setup_match=(scenario==intended) if intended else None
        topic_match=(raw['turns'][-1]['payload'].get('topic_id')==intended['topic_id']) if intended and 'topic_id' in intended and scenario else None
        instructor_match=state.get('support_state',{}).get('selected_instructor_id')=='instructor-11' if cid=='OP-03' and scenario else None
        validation_sources=[s for s in state.get('sources',[]) if s.get('validation_only')]
        observations.append({'test_id':cid,'input_overlay_present':scenario is not None,'input_overlay_matches_v2':setup_match,
            'selected_topic_sent':topic_match,'structured_instructor_selected':instructor_match,
            'runtime_source_bindings':refs,'operational_provenance_exact':provenance_match,
            'warning_metadata_present':bool(validation_sources) if refs else None,
            'ui_notice_rendered':None,'semantic_decision':None,'institutional_approval':None})
    return {'run_id':read(folder/'manifest.json')['run_id'],'contract_version':'2.0.0','observations':observations,
            'semantic_approvals':0,'human_acceptance':None,'interpretation':'Technical observations only; historical metrics are unchanged. Missing legacy overlays remain visible.'}

if __name__=='__main__':
    contract=read(PACKAGE/'contracts/2.0.0/contract.json')
    validate(contract,PACKAGE/'contracts/2.0.0')
    for name in ['sprint2-stabilization-full','sprint2-stabilization-v2-inputs']:
        folder=PACKAGE/'runs'/name
        (folder/'contract-v2-observations.json').write_text(json.dumps(observe(folder,contract),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

"""Prepare an additive v2 contract. Historical artifacts are read, never rewritten."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PACKAGE=ROOT/'docs/rag-quality'
OUT=PACKAGE/'contracts/2.0.0'
WORK=PACKAGE/'sprint2-stabilization'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protected=[]
    for folder in ['runs','audits','sprint2-fixes']:
        
        import os
        for base, dirs, files in os.walk(PACKAGE/folder, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {'.work','node_modules','__pycache__'} and not (Path(base)/d).is_symlink()]
            protected.extend(Path(base)/name for name in files)
    protected.extend(p for p in PACKAGE.iterdir() if p.is_file())
    
    if not (WORK/'historical-hashes-before.json').exists():
        save(WORK/'historical-hashes-before.json',{str(p.relative_to(ROOT)):digest(p) for p in sorted(set(protected))})
    baseline=PACKAGE/'runs/sprint2-fixes-verified-full'
    mapping=read(baseline/'document-crosswalk.json')
    inputs=read(PACKAGE/'sprint2-fixes/scenario-inputs.json')
    config=ROOT/'backend/app/support/operational_guidance.json'
    contract={
        'contract_version':'2.0.0', 'status':'technical_proposal_pending_human_acceptance',
        'baseline':{'run_id':read(baseline/'manifest.json')['run_id'],'dataset_version':'1.0.0',
                    'dataset_sha256':digest(PACKAGE/'rag_eval_dataset.jsonl'),
                    'evaluator_sha256':digest(PACKAGE/'quality.py'),
                    'schema_sha256':digest(PACKAGE/'evaluation_schema.json')},
        'inputs':inputs,
        'source_bindings':[{'runtime_document_id':d['runtime_document_id'],'alias':d['alias'],
                            'runtime_version':d['runtime_version'],'document_sha256':d['verified_blob_sha256'],
                            'scope':d['scope'],'validation_only':d['validation_only'],
                            'institutional_approval':'pending','historical_snapshot_equivalence':'not_established',
                            'chunks':[{'id':c['id'],'sha256':c['sha256'],'page':c['page'],'section':c['section'],'benefit_code':c['benefit_code']} for c in d['chunks']]}
                           for d in mapping if d['alias'] is not None],
        'operational_configuration':{'path':'backend/app/support/operational_guidance.json','sha256':digest(config),
                                     'origin':read(config)['origin'],'validation_status':read(config)['validation_status'],
                                     'institutional_approval':'pending','citation_kind':'operational_configuration',
                                     'pdf_citation_required':False,'instructor_action_scope':'education:contacts'},
        'warning_policy':{'documentary_channel':'source_metadata.validation_only',
                          'ui_render_verification':'pending_human_review',
                          'answer_body_warning_required_by_v2':False,
                          'historical_lexical_criterion':'preserved_and_reported_separately'},
        'scoring_policy':{'historical_evaluator':'unchanged','historical_scores':'immutable',
                          'cross_version_equivalence':False,'runtime_source_binding':'exact_version_document_hash_chunk_hash_and_id',
                          'operational_provenance':'exact_configuration_hash_and_origin_and_validation_status',
                          'semantic_approval':'human_decision_only','contract_checks':'observations_only_not_semantic_grades',
                          'comparability':'same_input_full_run_plus_separate_seven_case_input_overlay'},
        'review_protocol':{'dimensions':['fidelity','completeness','conditions_and_exceptions','citations','institutional_conflicts','access_restrictions'],
                           'reviewer':None,'decision':None,'reviewed_at':None,
                           'institutional_approval':'external_owner_required'}
    }
    save(OUT/'contract.json',contract)
    save(OUT/'scenario-inputs.json',inputs)
    schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:milioai:rag-evaluation-contract:2.0.0',
            'type':'object','additionalProperties':False,'required':list(contract),
            'properties':{k:{'type':'object'} for k in contract if k not in {'contract_version','status','source_bindings'}}}
    schema['properties'].update({'contract_version':{'const':'2.0.0'},'status':{'const':contract['status']},'source_bindings':{'type':'array','minItems':1,'items':{'type':'object','required':['runtime_document_id','runtime_version','document_sha256','chunks','historical_snapshot_equivalence'],'properties':{'historical_snapshot_equivalence':{'const':'not_established'}}}}})
    def replace_const(value):
        if isinstance(value,dict):
            if 'const' in value: value['enum']=[value.pop('const')]
            for child in value.values(): replace_const(child)
        elif isinstance(value,list):
            for child in value: replace_const(child)
    replace_const(schema)
    save(OUT/'schema.json',schema)
    save(OUT/'manifest.json',{'contract_sha256':digest(OUT/'contract.json'),'schema_sha256':digest(OUT/'schema.json'),'inputs_sha256':digest(OUT/'scenario-inputs.json'),'human_acceptance':None})

if __name__=='__main__': main()

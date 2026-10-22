"""Offline validation of additive contract and immutable historical bindings."""
import hashlib
import json
import re
import sys
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE))
import quality


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

def validate(contract,folder):
    schema=read(folder/'schema.json')
    quality.schema_definition_check(schema,schema)
    quality.schema_check(contract,schema,schema)
    assert contract['baseline']['dataset_sha256']==digest(PACKAGE/'rag_eval_dataset.jsonl')
    assert contract['baseline']['evaluator_sha256']==digest(PACKAGE/'quality.py')
    assert contract['baseline']['schema_sha256']==digest(PACKAGE/'evaluation_schema.json')
    assert contract['review_protocol']['decision'] is None
    assert contract['review_protocol']['reviewer'] is None
    assert contract['scoring_policy']['cross_version_equivalence'] is False
    required={'FP-05','FP-11','FP-13','FP-14','FP-15','FP-16','OP-03'}
    assert set(contract['inputs'])==required
    for key in required-{'OP-03'}:
        assert contract['inputs'][key]=={'topic_id':'folha_ponto'}
    setup=contract['inputs']['OP-03']['setup_turns']
    assert setup[0]['question_id']=='falta_curso.instrutor'
    assert [s['action']['kind'] for s in setup[1:]]==['instructor_known','instructor_select']
    assert setup[-1]['action']['instructor_id']=='instructor-11'
    root=PACKAGE.parents[1]
    op=contract['operational_configuration']
    assert op['sha256']==digest(root/op['path'])
    assert op['validation_status']==read(root/op['path'])['validation_status']
    assert op['institutional_approval']=='pending'
    assert op['pdf_citation_required'] is False
    baseline={d['runtime_document_id']:d for d in read(PACKAGE/'runs/sprint2-fixes-verified-full/document-crosswalk.json')}
    for binding in contract['source_bindings']:
        actual=baseline[binding['runtime_document_id']]
        assert binding['runtime_version']==actual['runtime_version']
        assert binding['document_sha256']==actual['verified_blob_sha256']
        assert re.fullmatch('[0-9a-f]{64}',binding['document_sha256'])
        assert binding['institutional_approval']=='pending'
        assert binding['historical_snapshot_equivalence']=='not_established'
        chunks={c['id']:c for c in actual['chunks']}
        for chunk in binding['chunks']:
            assert chunk['sha256']==chunks[chunk['id']]['sha256']
    manifest=read(folder/'manifest.json')
    assert manifest['contract_sha256']==digest(folder/'contract.json')
    assert manifest['schema_sha256']==digest(folder/'schema.json')
    assert manifest['inputs_sha256']==digest(folder/'scenario-inputs.json')
    return {'contract_version':contract['contract_version'],'structure_and_bindings':'verified','human_acceptance':None,'semantic_approvals':0}

if __name__=='__main__':
    folder=PACKAGE/'contracts/2.0.0'
    print(json.dumps(validate(read(folder/'contract.json'),folder),ensure_ascii=False,indent=2))

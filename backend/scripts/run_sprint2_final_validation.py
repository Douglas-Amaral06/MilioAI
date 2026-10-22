"""Sequential final checks; each stage has its own raw results and source signature."""
import json
import subprocess
import sys
from pathlib import Path

base=Path('/tmp/sprint2-stabilization')
package=base/'docs/rag-quality'
stages=[
    ('boundaries',[sys.executable,'-m','app.rag.evaluate_real','--package',str(package),'--output',str(package/'runs/sprint2-stabilization-boundaries'),'--ids','FP-04,FP-07,FP-12']),
    ('v2-inputs',[sys.executable,'-m','app.rag.evaluate_real','--package',str(package),'--output',str(package/'runs/sprint2-stabilization-v2-inputs'),'--scenario-contract',str(package/'contracts/2.0.0/scenario-inputs.json'),'--ids','FP-05,FP-11,FP-13,FP-14,FP-15,FP-16,OP-03']),
    ('final-stability',[sys.executable,'check_fp07_stability.py','--output',str(base/'stability-final-list-context')]),
]
for name,command in stages:
    (base/'validation-stage.json').write_text(json.dumps({'stage':name,'state':'running'}))
    with (base/(name+'-execution.log')).open('w') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
(base/'validation-stage.json').write_text(json.dumps({'state':'complete'}))

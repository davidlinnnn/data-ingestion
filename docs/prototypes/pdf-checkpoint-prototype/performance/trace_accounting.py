"""Fast deterministic accounting loop over the captured real execution trace."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent.parent
E=R/'k8s/evidence-linux'
native=json.loads((E/'native-baseline-metrics.json').read_text())
run=json.loads((E/'normal-result.json').read_text())
ledger=json.loads((E/'normal-ledger.json').read_text())
resources=json.loads((E/'child-resource-summary.json').read_text())['normal']
accepted=[e for e in ledger if e['event']=='registered']
ocr=next(e for e in accepted if e['kind']=='ocr')
child=resources['accepted_child_process_wall_seconds_sum']
assert len(accepted)==13 and run['wall_seconds']>=child
assert child>native['wall_seconds'], 'The captured grouped child-cost difference disappeared'
result={'historical_scope_mismatch':True,'native_process_without_enrichment_s':native['wall_seconds'],
'grouped_temporal_with_enrichment_s':run['wall_seconds'],'parsing_and_assembly_children_s':child,
'ocr_activity_including_parent_and_store_s':ocr['seconds'],
'outside_parsing_assembly_children_and_ocr_activity_s':run['wall_seconds']-child-ocr['seconds'],
'interpretation':'Already 40.69 seconds more elapsed inside parsing/assembly child processes; cannot attribute the whole gap to Temporal. Need matched direct/Temporal trials.'}
print(json.dumps(result,indent=2))

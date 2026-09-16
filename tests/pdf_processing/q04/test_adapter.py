"""Consumer-result and orchestration contracts; no services or model inference."""
import copy
import json
from pathlib import Path
import unittest
from consumer import check_graph

class GraphChecks(unittest.TestCase):
    def test_picture_child_and_unlinked_content_cannot_disappear(self):
        root = Path('/private/tmp/t06-final-results')
        doc = json.loads((root/'09-document.json').read_text())
        report = json.loads((root/'09-evidence.json').read_text())
        self.assertGreater(check_graph(doc, report)['items'], 0)
        bad = copy.deepcopy(report)
        bad['items'].pop()
        with self.assertRaises(ValueError):
            check_graph(doc, bad)


from consumer import check_fixture
from contracts import mode_checks, drain_checks, warm_checks, validate_window
from telemetry import check_coverage, check_sample

class SourceOracles(unittest.TestCase):
    def test_retained_non_aima_source_oracles_and_mutations(self):
        root = Path('/private/tmp/t06-final-results')
        oracle = Path('/private/tmp/q04-inputs-local-v1/oracles')
        for sid in ('06', '07', '09', '10'):
            with self.subTest(sid=sid):
                doc = json.loads((root/(sid+'-document.json')).read_text())
                report = json.loads((root/(sid+'-evidence.json')).read_text())
                self.assertGreater(check_fixture(sid, doc, report, None, None, oracle)['items'], 0)
                bad = copy.deepcopy(report)
                bad['items'][-1]['text'] = 'corrupt'
                with self.assertRaises(ValueError):
                    check_fixture(sid, doc, bad, None, None, oracle)

    def test_graph_rejects_child_caption_provenance_and_cell_corruption(self):
        root = Path('/private/tmp/t06-final-results')
        doc = json.loads((root/'06-document.json').read_text())
        report = json.loads((root/'06-evidence.json').read_text())
        mutations = [lambda d: d['body']['children'].append({'$ref':'#/texts/absent'}),
            lambda d: d['tables'][0]['data']['table_cells'][0].update(row_span=99),
            lambda d: d['pictures'][0].update(captions=[{'$ref':'#/texts/absent'}]),
            lambda d: d['texts'][0]['prov'][0].update(page_no=999)]
        for mutate in mutations:
            bad = copy.deepcopy(doc); mutate(bad)
            with self.assertRaises((ValueError, KeyError)):
                check_graph(bad, report)

class RecoveryContracts(unittest.TestCase):
    def test_drain_rejects_missing_retained_groups_and_wrong_retry(self):
        result = {'steps':[{'stage':'group','operation':str(i)} for i in range(11)]}
        attempts = [{'range':[i,min(i+4,51)],'attempt':2 if i==6 else 1} for i in range(1,52,5)]
        self.assertEqual(drain_checks(attempts, ['0'], result)['retried_range'], [6,10])
        for start, attempt in ((1,2),(6,1),(11,2)):
            bad = copy.deepcopy(attempts)
            next(x for x in bad if x['range'][0]==start)['attempt']=attempt
            with self.assertRaises(ValueError): drain_checks(bad,['0'],result)
        with self.assertRaises(ValueError): drain_checks(attempts,[],result)
        with self.assertRaises(ValueError): drain_checks(attempts[:-1],['0'],result)

    def test_warm_requires_real_continuity_and_request_twenty_recycle(self):
        results=[]; offset=0
        for sid,count in [('06',6),('07',3),('08',3),('native',11),('06',6)]:
            steps=[]
            for i in range(offset,offset+count):
                steps.append({'stage':'group','parser':{'pid':100 if i<20 else 200,
                    'restarts':1 if i<20 else 2,'recycles':0 if i<19 else 1}})
            results.append({'sid':sid,'result':{'steps':steps}});offset+=count
        self.assertEqual(warm_checks(results)['groups'],29)
        bad=copy.deepcopy(results);bad[1]['result']['steps'][0]['parser']['pid']=999
        with self.assertRaises(ValueError): warm_checks(bad)
        with self.assertRaises(ValueError): warm_checks(results[:-1])

    def test_resource_loss_oom_and_stale_authorization_fail_closed(self):
        rows=[{'time':i,'available':100,'memory_current':20,'vm_oom_kill':2,
            'memory_events':{'oom_kill':0},'psi_full_avg10':0} for i in (10,11,12)]
        limits={'min_available_bytes':50,'max_cgroup_bytes':30,'max_full_psi':0}
        check_sample(rows[-1],rows[0],limits)
        self.assertEqual(check_coverage(rows,10,12,2)['samples'],3)
        for bad in [[],rows[1:],rows[:-1]]:
            with self.assertRaises(ValueError): check_coverage(bad,10,12,2)
        for key,value in [('vm_oom_kill',3),('available',0),('memory_current',31),('psi_full_avg10',.1)]:
            with self.assertRaises(ValueError): check_sample({**rows[-1],key:value},rows[0],limits)
        with self.assertRaises(ValueError): validate_window({'approval_reference':'old','owner':'x','starts_at':1,'ends_at':9},10)

import tempfile
from consumer import check_reference, graph_projection

class FullFixtureGraphs(unittest.TestCase):
    def test_all_retained_graphs_and_missing_picture_children_fail(self):
        root = Path('/private/tmp/q04-inputs-local-v2')
        for sid in ('native','06','07','09','10'):
            with self.subTest(sid=sid), tempfile.TemporaryDirectory() as out:
                doc = json.loads((root/'references'/(sid+'.json')).read_text())
                report = json.loads((Path('/private/tmp/q04-retained-content-v1')/(sid+'.json')).read_text())
                checks = check_fixture(sid,doc,report,None,None,root/'oracles')
                self.assertGreater(checks['items'],0)
                check_reference(doc,doc,Path(out))
                bad=copy.deepcopy(doc)
                bad['furniture']['children']=[]
                if bad==doc:
                    bad['texts'].pop()
                with self.assertRaises(ValueError): check_reference(bad,doc,Path(out))
                self.assertTrue((Path(out)/'graph-delta.json').exists())

    def test_exact_aima_corrected_graph_and_eight_reviewed_edges(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'q02'))
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'q03'))
        from pdf_processing.evidence import execute
        from q03_fixtures import policy
        from pdf_processing.relationships import build
        from docling_core.types.doc import DoclingDocument
        root=Path('/private/tmp/q04-inputs-local-v2')
        reference=json.loads((root/'references/08.json').read_text())
        with tempfile.TemporaryDirectory(prefix='q04-aima-render-') as tmp:
            tmp=Path(tmp)
            DoclingDocument.model_validate(reference).save_as_json(tmp/'document.json')
            doc=json.loads((tmp/'document.json').read_text())
            source={'version':3,'source_revision':'q04-local-supporting','artifact':{'sha256':'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980'}}
            execute({'out':str(tmp/'evidence'),'parsed':str(tmp/'document.json'),'pdf':str(root/'fixtures/08.pdf'),
                'source':source,'parsed_result':'parsed','assembly':'assembly','review':{},
                'policy':'typed-source-relationships-v2','relationships':policy(),'renderer_version':'local-test','max_render_pixels':20000000})
            report=json.loads((tmp/'evidence/content-evidence.json').read_text())
            relations=build(doc,source,'parsed','assembly',policy())
            check_reference(doc,reference,tmp)
            checks=check_fixture('08',doc,report,relations,policy(),root/'oracles')
            self.assertEqual(checks['algorithms'],4)
            self.assertEqual(checks['continuation_edges'],8)
            bad=copy.deepcopy(relations);bad['resolved'][0]['members'][-1]['role']='body'
            with self.assertRaises((ValueError,AssertionError)):
                check_fixture('08',doc,report,bad,policy(),root/'oracles')

    def test_independent_table_oracle_rejects_self_consistent_corruption(self):
        root=Path('/private/tmp/q04-inputs-local-v2')
        doc=json.loads((root/'references/06.json').read_text())
        report=json.loads(Path('/private/tmp/q04-retained-content-v1/06.json').read_text())
        doc['tables'][0]['data']['table_cells'][0]['text']='incorrect but internally consistent'
        with self.assertRaises(ValueError): check_fixture('06',doc,report,None,None,root/'oracles')

class ModeContracts(unittest.TestCase):
    def test_restore_replay_and_invalidation_have_non_vacuous_identity_checks(self):
        fresh={'status':'complete','pages':1,'selected_components':0,'registered_components':0,
            'processing_result':'final-1','steps':[{'stage':'group','operation':'g1','reused':False},
                {'stage':'assembly','operation':'a1','reused':False}]}
        accepted={'document_sha256':'doc','final':{'content_evidence':'e1'}}
        previous={'result':fresh,'accepted':accepted}
        mode_checks('fresh',fresh,accepted)
        restored=copy.deepcopy(fresh)
        for step in restored['steps']:step['reused']=True
        restored['processing_result']='final-2'
        next_accepted={'document_sha256':'doc','final':{'content_evidence':'e2'}}
        mode_checks('restored',restored,next_accepted,previous)
        replay=copy.deepcopy(restored);replay['processing_result']='final-1'
        mode_checks('replay',replay,accepted,previous)
        invalidated=copy.deepcopy(fresh);invalidated['processing_result']='final-3'
        for step in invalidated['steps']:step['operation']+='-changed'
        mode_checks('invalidation',invalidated,next_accepted,previous)
        for mode,result,value in [('restored',fresh,next_accepted),('replay',restored,accepted),
                ('invalidation',fresh,next_accepted),('fresh',{**fresh,'steps':[]},accepted),
                ('restored',restored,accepted)]:
            with self.subTest(mode=mode),self.assertRaises(ValueError):mode_checks(mode,result,value,previous)

    def test_missing_or_reused_selected_ocr_cannot_pass(self):
        result={'pages':1,'selected_components':1,'registered_components':1,'steps':[
            {'stage':'group','operation':'g','reused':False}, {'stage':'assembly','operation':'a','reused':False}]}
        with self.assertRaises(ValueError):mode_checks('fresh',result,{})
        result['steps'].append({'stage':'component_ocr','operation':'ocr','reused':True})
        with self.assertRaises(ValueError):mode_checks('fresh',result,{})

if __name__ == '__main__':
    unittest.main()

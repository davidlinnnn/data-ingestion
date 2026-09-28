"""S2 source-grounded expectations through the actual final-result interface."""
import asyncio,hashlib,json,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t06','final')
    client=await Client.connect('temporal:7233');out=Path('/tmp/t06-results');out.mkdir(exist_ok=True)
    def read(identity,name):
        manifest=store.resolve(identity)
        return store.read_artifact(next(f for f in manifest['files'] if f['name']==name))
    norm=lambda s:' '.join(s.split())
    results={}
    for entry in json.loads(Path('/tmp/t06-fixtures/manifest.json').read_text()):
        sid=entry['id'];data=Path('/tmp/t06-fixtures',sid+'.pdf').read_bytes();key='final/sources/'+sid+'.pdf'
        assert digest(data)==entry['review']['source_sha256']
        saved=s3.put_object(Bucket='t06',Key=key,Body=data)
        request={'version':3,'completion':'required_evidence_v1','profile':'native-v1','request_id':uuid.uuid4().hex,
            'source_revision':'bounded:'+entry['source_revision'],
            'artifact':{'key':key,'name':sid+'.pdf','version_id':saved['VersionId'],'sha256':digest(data)}}
        saved_request=out/(sid+'-request.json')
        if saved_request.exists():
            request=json.loads(saved_request.read_text())
        else:
            saved_request.write_text(json.dumps(request))
        handle=await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t06-pdf'},id=uuid.uuid4().hex,task_queue='t06-workflows')
        result=await handle.result()
        (out/(sid+'-workflow.json')).write_text(json.dumps(result,indent=2))
        assert result['status']=='complete',result
        final=json.loads(read(result['processing_result'],'processing-result.json'))
        report=json.loads(read(final['content_evidence'],'content-evidence.json'))
        raw=read(final['assembly'],'document.json');doc=json.loads(raw)
        assert digest(raw)==report['document_sha256']
        assert report['source']==request and report['parsed_result']==final['parsed_result']
        assert digest(read(final['content_evidence'],'source.pdf'))==request['artifact']['sha256']
        assert digest(read(final['content_evidence'],'original-source.pdf'))==entry['original_sha256']
        for p in report['pages'].values():
            assert digest(read(final['content_evidence'],p['artifact']))==p['sha256']
            assert p['original_physical_page']==entry['review']['original_pages'][str(p['physical_page'])]
        assert len({n['ref'] for n in report['items']})==len(report['items'])
        checks={'durable_sources_pages':True,'unique_typed_refs':len(report['items'])}
        if sid in ('06','07'):
            expected=json.loads(Path('/tmp/t06-oracles',sid+'-table-full-audit.json').read_text())
            table=next(t for t in doc['tables'] if t['data']['num_rows']==(26 if sid=='06' else 15))
            cells={(c['start_row_offset_idx'],c['start_col_offset_idx']):c for c in table['data']['table_cells']}
            for e in expected:
                actual=cells[(e['row'],e['col'])]
                # Source-reviewed S2 disposition for these exact cells only:
                # PDF font U+0002 plus discretionary line-break spacing.
                source=e['parsed_text'] if sid=='07' and '\x02' in e['source_text'] else e['source_text']
                assert norm(actual['text'])==norm(source),(sid,e['row'],e['col'])
                assert actual['row_span']==e['rowspan']
            checks['complete_table_cells']=len(expected)
        if sid=='08':
            old=json.loads(Path('/tmp/t06-oracles/08-86.json').read_text())
            code=next(t for t in old['texts'] if t['self_ref']=='#/texts/11')
            actual=next(t for t in report['items'] if t['actual_type']=='code' and norm(t['text'])==norm(code['text']))
            assert actual['captions'] and actual['regions']
            notes=[x for x in report['items'] if x['actual_type']=='footnote']
            assert len(notes)>=2
            assert report['representation_observations']
            checks.update(code_complete=True,footnotes=len(notes),representation_uncertainty=True)
        if sid=='09':
            occurrences=[x for x in report['formula_occurrences'] if x.get('review_id','').startswith('eq')]
            assert len(occurrences)==6,occurrences
            equation2=next(x for x in occurrences if x['review_id']=='eq2')
            typed={x['ref']:x for x in report['items']}
            assert any(typed[r]['actual_type']=='text' for r in equation2['refs']),equation2
            assert report['representation_observations']
            checks.update(formula_occurrences=6,textitem_formula=True,representation_uncertainty=True)
        if sid=='10':
            oracle=json.loads(Path('/tmp/t06-oracles/new-source-oracle.json').read_text())
            expected=next(x for x in oracle if x['source_id']=='10')['regions']
            texts=[norm(x['text']) for x in report['items'] if x.get('text')]
            for region in expected:
                l,t,r,b=region['bbox'];pieces=[]
                for item in report['items']:
                    if not item.get('text'):continue
                    for g in item['regions']:
                        x1,y1,x2,y2=g['bbox_top_left_points']
                        if g['page']==1 and l<=(x1+x2)/2<=r and t<=(y1+y2)/2<=b:
                            pieces.append((y1,x1,item['text']));break
                # A source textbox may be split into several typed child items.
                actual=' '.join(x[2] for x in sorted(pieces))
                assert norm(region['expected_text'])==norm(actual),(region['id'],actual)
            assert len(expected)==27,len(expected)
            checks['complete_textboxes']=len(expected)
        (out/(sid+'-document.json')).write_bytes(raw)
        (out/(sid+'-evidence.json')).write_text(json.dumps(report))
        results[sid]={'workflow_id':handle.id,'request':request,'result':result,'checks':checks,
                      'document_sha256':digest(raw),'content_evidence':final['content_evidence']}
        (out/'summary.json').write_text(json.dumps(results,indent=2))
        print(sid,checks,flush=True)
if __name__=='__main__':asyncio.run(main())

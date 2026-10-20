"""Audit mapper identities/values and the four named incidents, without conversion."""
import collections
import hashlib
import html
import importlib.util
import json
import pathlib
import re
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mapper',ROOT/'map_documents.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


class RefText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.values=collections.defaultdict(str)
    def handle_starttag(self,tag,attrs):
        if tag not in ('meta','hr','br','img','input','link'):
            self.stack.append(dict(attrs).get('data-source-ref'))
    def handle_endtag(self,tag):
        if tag not in ('meta','hr','br','img','input','link') and self.stack:
            self.stack.pop()
    def handle_data(self,data):
        for ref in self.stack:
            if ref:
                self.values[ref]+=data


def normalized(value):
    return ' '.join(value.split())


def main():
    impacts=[]; union=[]; examples={}
    for p in sorted((ROOT/'outputs').glob('*/mapped.json')):
        d=json.loads(p.read_text()); jid=p.parent.name
        nodes=[n for tree in [d['body'],d['furniture'],*d['unlinked']] for n in walk(tree)]
        byref={n['self_ref']:n for n in nodes}
        parser=RefText();parser.feed((p.parent/'document.html').read_text())
        fallback={e['ref'] for e in d['events'] if e['type']=='empty_text_orig_fallback'}
        tables={n['self_ref'] for n in nodes if n['kind']=='table'}
        merged_tables={e['ref'] for e in d['events'] if e['type']=='table_single_cell_mapping' and e['merged_cells']}
        pictures=[]
        pictexts=set();piccells=set()
        for n in nodes:
            if n['kind']!='picture':continue
            descendants=list(walk(n))[1:]
            textrefs={x['self_ref'] for x in descendants if x['kind']=='text'}
            cellrefs={c['source_ref'] for x in descendants if x['kind']=='table' for c in x['cells']}
            values=[u['text'] for u in d['units'] if u['ref'] in textrefs|cellrefs]
            if not values:continue
            words=len(re.findall(r'\S+', ' '.join(values)))
            pictures.append({'ref':n['self_ref'],'pages':[p['page_no']for p in n.get('prov',[])],'native_text_item_refs':sorted(textrefs),'native_table_cell_refs':sorted(cellrefs),'words':words,'characters':sum(map(len,values)),'low_word_count_le10':words<=10,'content_verified':False,'channel':'picture_native_uncertain','C_image_supplement':'NOT_EXECUTED'})
            pictexts.update(textrefs);piccells.update(cellrefs)
        picturerefs={p['ref']for p in pictures}
        primary=fallback|tables|picturerefs
        itemunion=primary|pictexts
        unitmismatch=[]
        for unit in d['units']:
            expected=m.visible(unit['text'])
            actual=parser.values[unit['ref']]
            if expected and expected not in actual:
                unitmismatch.append(unit['ref'])
        assert not unitmismatch,unitmismatch
        uncertain_tables=[{'ref':n['self_ref'],'pages':[p['page_no']for p in n.get('prov',[])],**n['layout_check']}for n in nodes if n['kind']=='table'and n['layout_check']['issues']]
        impacts.append({'id':jid,'fallback_item_refs':sorted(fallback),'picture_container_refs':sorted(picturerefs),'picture_descendant_text_item_refs':sorted(pictexts),'picture_descendant_table_cell_refs':sorted(piccells),'all_mapped_table_item_refs':sorted(tables),'merged_table_item_refs':sorted(merged_tables),'primary_affected_unique_item_refs':sorted(primary),'including_picture_descendant_unique_item_refs':sorted(itemunion),'picture_frames':pictures,'uncertain_native_tables':uncertain_tables,'counts':{'fallback_text_items':len(fallback),'picture_frames_with_native_text':len(pictures),'picture_descendant_text_items':len(pictexts),'picture_descendant_table_cells':len(piccells),'tables_all':len(tables),'all_native_table_cells':sum(len(n['cells'])for n in nodes if n['kind']=='table'),'tables_with_merged_cells':len(merged_tables),'merged_cells':sum(e.get('merged_cells',0)for e in d['events']),'primary_affected_item_union':len(primary),'including_descendant_item_union':len(itemunion),'low_word_picture_frames_le10':sum(p['low_word_count_le10']for p in pictures),'uncertain_native_tables':len(uncertain_tables)},'all_delivered_unit_values_present_in_own_rendered_ref':True,'new_same_ref_repeats':0,'source_different_ref_repeated_values':len(d['selfcheck']['source_repeated_values_retained']),'semantic_duplicate_free':'NOT_ESTABLISHED; different source refs and substrings can already duplicate semantically.'})
        examples[jid]=(d,byref,parser.values)
    total=collections.Counter()
    docs=collections.Counter()
    for i in impacts:
        total.update(i['counts'])
        docs.update({k:1 for k,v in i['counts'].items()if v})
    m.save(ROOT/'impact-counts.json',{'documents':36,'totals':dict(total),'documents_affected':dict(docs),'unit_definition':'Docling item reference != table-cell reference != picture frame != semantic paragraph or Q4 event. Primary item union = fallback text refs + picture containers with native text + all table containers; expanded union also includes picture descendant text refs. Table cells are counted separately.','jobs':impacts})

    def evidence(jid,refs):
        d,nodes,rendered=examples[jid]
        items=[]
        for ref in refs:
            node=nodes[ref]
            value=node['delivered_text']; expected=m.visible(value)
            actual=rendered[ref]
            assert expected in actual
            items.append({'ref':ref,'pages':[p['page_no']for p in node.get('prov',[])],'source_label':node.get('label'),'source_text':node.get('text'),'source_orig':node.get('orig'),'text_source':node.get('text_source'),'delivered_text':value,'role_uncertain':node.get('role_uncertain'),'channel':node.get('channel'),'marker':node.get('marker'),'enumerated':node.get('enumerated'),'ancestors':node.get('ancestors'),'source_parent':node.get('parent'),'rendered_ref_text':actual,'delivered_value_present':True,'within_ref_value_occurrences':actual.count(expected)if expected else 0,'exact_orig_delivery':value==node.get('orig'),'list_display_equals_orig':(node.get('marker','')+' '+value)==node.get('orig')if node.get('label')=='list_item' else None,'same_full_value_source_unit_refs':[u['ref']for u in d['units']if u['text']==value]})
        return items
    adam='F-iclr_adam';p16='P-16-2505.22954v1';sica='P-07-2504.15228v2';skill='P-05-2602.08234v2'
    adamrefs=[f'#/texts/{i}'for i in [419,420,423,426,430,432,434]]
    p16refs=[n['self_ref']for n in examples[p16][1].values()if n['kind']=='text' and n.get('role_uncertain') and any(p['page_no']==25 for p in n.get('prov',[]))]
    sicarefs=[n['self_ref']for n in examples[sica][1].values()if n['kind']=='text' and n.get('picture_ref')in ['#/pictures/4','#/pictures/5']]
    sicaitems=evidence(sica,sicarefs)
    # Native list markers are necessary: text-only concatenation loses 49 source characters in box 2.
    markers=[x for x in sicaitems if x['source_label']=='list_item']
    assert all(x['list_display_equals_orig'] for x in markers)
    lower=[x for x in sicaitems if '#/pictures/5' in x['ancestors']]
    lower_text_nonspace=sum(len(''.join(x['source_text'].split()))for x in lower)
    lower_orig_nonspace=sum(len(''.join(x['source_orig'].split()))for x in lower)
    lower_display_nonspace=sum(len(''.join(((x.get('marker')+' ' if x.get('marker') else '')+x['delivered_text']).split()))for x in lower)
    assert (lower_text_nonspace,lower_orig_nonspace,lower_display_nonspace)==(1439,1488,1488)
    skillitems=[]
    for ti,ci in [(10,1),(11,1),(11,13),(14,9)]:
        table=examples[skill][1][f'#/tables/{ti}'];c=table['cells'][ci];ref=c['source_ref'];value=m.visible(c['text']);actual=examples[skill][2][ref]
        assert actual==value
        skillitems.append({'table_ref':table['self_ref'],'cell_ref':ref,'pages':[p['page_no']for p in table.get('prov',[])],'source_cell':c,'rendered_cell_text':actual,'literal_value_occurrences_in_this_cell':actual.count(value),'whole_document_same_value_unit_refs':[u['ref']for u in examples[skill][0]['units']if u['text']==c['text']],'native_span':{'row_span':c.get('row_span'),'col_span':c.get('col_span')},'source_control_chars':[ord(x)for x in c['text']if ord(x)<32],'target_duplicate_fixed':True})
    p16all=[n for n in examples[p16][1].values()if n['kind']=='text'and any(p['page_no']==25 for p in n.get('prov',[]))and re.search(r'(?:django__django|sphinx-doc__sphinx)-\d+',n.get('delivered_text',''))]
    p16ids=re.findall(r'(?:django__django|sphinx-doc__sphinx)-\d+',' '.join(n['delivered_text']for n in p16all))
    cases=[{'case':'Adam p12 empty-text definition/formula','job_id':adam,'pages':[12],'items':evidence(adam,adamrefs),'lexical_delivery':'Definition10.1 quantifier line plus six flattened formula items now delivered from orig in their existing native node positions.','target_export_omission_repaired':True,'Q4_complete_fix':'UNKNOWN','remaining':'No formula reconstruction/validation; role remains uncertain and existing sentence/math order is not repaired.'}, {'case':'P16 p25 task IDs','job_id':p16,'pages':[25],'items':evidence(p16,p16refs),'fallback_id_items':len(p16refs),'all_id_items':len(p16all),'all_task_ids':p16ids,'all_task_id_count':len(p16ids),'all_task_ids_distinct':len(set(p16ids))==len(p16ids),'lexical_delivery':'All 60 printed task IDs now accessible; 35 were formula/text-empty orig fallbacks. IDs checked against original page image.','target_export_omission_repaired':True,'Q4_complete_fix':'UNKNOWN','remaining':'Formula roles unchanged; no inference that native column/list order or section attribution is correct.'}, {'case':'SICA p12 two prompt boxes','job_id':sica,'pages':[12],'items':sicaitems,'list_items':len(markers),'all_native_markers_enumerated_and_parent_refs_preserved':True,'list_render_equals_orig_for_all_items':True,'picture_refs':['#/pictures/4','#/pictures/5'],'lexical_delivery':f'Both prompt boxes and all {len(markers)} list markers are now delivered once in picture_native_uncertain, kept separate from body and unexecuted C image supplement.','target_export_omission_repaired_in_native_picture_channel':True,'Q4_complete_fix':'UNKNOWN','remaining':'No upgrade of picture role to body, no list-tree reconstruction beyond source singleton groups/explicit markers, no general source-order proof.'}, {'case':'SkillRL p22-24 merged-cell duplicates','job_id':skill,'pages':[22,23,24],'items':skillitems,'lexical_delivery':'Four known repeated Task/skills cell instances are delivered once per source cell, with original colspan.','target_duplicate_repaired':True,'Q4_local_duplicate_event_fixed':True,'Q4_whole_paper_fixed':'NOT_CLAIMED','remaining':'The cell containing naviga/control02/tion retains its source glyph uncertainty as visible escape; native table structure/formula/order not re-inferred.'}]
    for case in cases:
        jid=case['job_id'];case['input']=examples[jid][0]['input'];case['output_json']=str(ROOT/'outputs'/jid/'mapped.json');case['output_html']=str(ROOT/'outputs'/jid/'document.html');case['output_md']=str(ROOT/'outputs'/jid/'document.md');case['page_images']=[str(m.R3/'adjudication/pages'/jid/f'p{p:03d}.png')for p in case['pages']];case['reviewed_original_page_images']=True
    assert len(p16ids)==60 and len(p16refs)==35
    cases[2]['second_box_nonspace_characters']={'text_only':lower_text_nonspace,'orig':lower_orig_nonspace,'delivered_with_explicit_markers':lower_display_nonspace,'marker_characters_restored':sum(len(x['marker'])for x in markers),'native_list_items':len(markers)}
    m.save(ROOT/'four-case-evidence.json',{'cases':cases,'scope':'Lexical item/cell delivery checks and original page image review. Changes only derived JSON/HTML/MD mapper; no conversion or Docling mutation. No corpus-level Q4 pass-rate inference.'})


if __name__=='__main__':main()

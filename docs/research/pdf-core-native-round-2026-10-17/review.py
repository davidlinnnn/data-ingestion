"""Persist source-based manual adjudication; checks do not repair candidate outputs."""
import collections
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
contract=json.loads((REPO/"docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json").read_text())
assert len(contract["units"])==41
assert hashlib.sha256((REPO/"docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json").read_bytes()).hexdigest()=="22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2"

def save(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")

# Fixed item mappings come from inspection of this round's typed documents and original source regions.
standard_wiki={357:[5],361:[9],362:[10],363:[11],366:[14],367:[15],368:[16]}
standard_dgm={646:[0],648:[2],649:[3],650:[4],651:[5],652:[6]}
standard_seal={21:[69],23:[71],24:[72],25:[73],26:[74],28:[76],30:[78],32:[80],45:[92],46:[93],47:[94],49:[96],52:[99],53:[100],33:[81],34:[82,92],48:[95],50:[97],51:[98]}
egret_seal={21:[70],23:[72],24:[73],25:[74],26:[75],28:[77],30:[79],32:[81],45:[84],46:[85],47:[86],49:[88],52:[90],53:[91],33:[82],34:[83,84],48:[87],50:[89],51:[]}
standard_controls={0:[6],1:[8],2:[10],1001:[1],4:[4],12:[12],13:[12],14:[13,14],15:[15]}
egret_controls={0:[6],1:[8],2:list(range(10,17)),1001:[1],4:[4],12:[18],13:[18],14:[19,20],15:[21]}
c1_dgm={646:[],648:[1],649:[2],650:[],651:[3],652:[]}
c1_seal={21:[0],23:[1],24:[2],25:[3],26:[4],28:[6],30:[8,10],32:[11],45:[13],46:[16],47:[17],49:[19],52:[22],53:[23],33:[12],34:[13,14],48:[18],50:[20],51:[21]}
c1_controls={0:[6],1:[8],2:[10],1001:[1],4:[4],12:[12],13:[12],14:[13],15:[14]}
f13={"wikiskill":{361,362,363},"dgm":set(),"seal":{30,32,33,34,46,47,48,49,50,51,52},"controls":{0,1,2,4}}
f14={"wikiskill":set(),"dgm":{646,648,650,652},"seal":set(),"controls":{12,13,14}}
records=[]
for profile in ["C1","S0","S1"]:
    docs={s:json.loads((HERE/profile/s/"document.json").read_text()) for s in ["wikiskill","dgm","seal","controls"]}
    for u in contract["units"]:
        source=u["source"]
        number=int(u["native_target_refs"][0].split("/")[-1])
        if source=="controls" and number==1 and "paragraph" in u["job_id"]:number=1001
        if profile=="C1":
            mapping={"wikiskill":{},"dgm":c1_dgm,"seal":c1_seal,"controls":c1_controls}
        else:
            mapping={"wikiskill":standard_wiki,"dgm":standard_dgm,"seal":standard_seal if profile=="S0" else egret_seal,"controls":standard_controls if profile=="S0" else egret_controls}
        matched=[docs[source]["texts"][i] for i in mapping[source].get(number,[])]
        status="pass"
        findings=[]
        raw_status=None
        if profile=="C1":
            raw_status="pass"
            if source=="wikiskill":
                status=raw_status="runtime_failure"
                findings=["Range failed with Unicode subset KeyError; no raw or typed page result survived the official pipeline. All seven units remain in denominator; not seven model accuracy failures."]
            elif source=="dgm":
                if number==646:
                    status=raw_status="material"
                    findings=["Raw misclassifies diff as LaTeX table; newline escape becomes _n, f-string get(...,0) becomes 0}, final condition loses if and changes zero/continuation, context indentation lost. Typed/Markdown diff missing; table parser also lacks pylatexenc."]
                elif number in {650,652}:
                    status="missing_dependency"
                    findings=["Complete quoted source instructions are present in raw table cells; visible source wrap arrows can reflow under original rule. Official table parser drops the block because pylatexenc is absent; delivery missing, not evidence of missing model transcription."]
                else:findings=["Complete prose/label retained; E04 five ordered tokens, both node actions and 23.3%/40.5% bindings retained. Printer hyphenation may reflow."]
            elif source=="seal":
                if number==21:
                    status=raw_status="material"
                    findings=["Only p3 suffix survives. p2 generated repetitive incomplete table to 9001 reported tokens versus cap9000, missing Knowledge Updating prefix; no completed class token for that text."]
                elif number==30:
                    status="material";findings=["Both raw page fragments retained, but typed/Markdown split at questions and / associated answers, with page number between. Plain C/italic roles and escaped math wrappers do not deliver all11inlineLaTeX spans in one paragraph."]
                elif number in {32,34,46,47,49,52}:
                    status="material";findings=["Full source prose and raw math/HTML relationships retained; official parser flattens sup/sub and strips inline math backslashes, stock Markdown escapes underscores, so required inline LaTeX is not delivered."]
                    if number==34:findings.append("Unlike paragraph and separate Algorithm1 heading are distinguished; suffix joined before heading, a structural improvement over S0/S1, without repairing the remaining math delivery.")
                elif number in {33,48,50}:
                    status="material";findings=["Raw core display math and original equation number are retained. Typed formula still includes parenthesized LaTeX delimiters and stock export wraps it in $$ ... $$, producing nested math delimiters; usable stock formula delivery fails."]
                elif number==51:
                    status=raw_status="material";findings=["Raw history y_<s loses < and becomes y_ s; expression meaning regresses. Stock formula additionally nests parenthesized LaTeX delimiters in $$ ... $$."]
                else:findings=["Entire source target prose retained under allowed typography/wrap normalization; no new target boundary required."]
            else:
                if number==0:
                    status=raw_status="material";findings=["Raw matrix becomes newline list1,-2,3,4 with M; 2x2 bracket/row-column structure missing, typed plain text."]
                elif number in {1,2}:
                    status="material";findings=["Raw fraction/cases mathematics retained; stock export nests parenthesized LaTeX delimiters within $$ ... $$."]
                elif number==4:
                    status="material";findings=["Raw x<sup>2</sup> retains exponent, typed/Markdown becomes x2; full inline y=x^2+1 LaTeX absent."]
                elif number==12:
                    status="material";findings=["Raw source #comment retained; parser removes leading # and folds the following body into prose."]
                elif number==13:
                    status=raw_status="material";findings=["Raw six lines lose all required0/4/4/8/0/4 indentation; parser then flattens code to prose."]
                else:findings=["Source sentence/inline operator and literal retained in context; Markdown HTML escaping of <= is not an operator error."]
        else:
            if number in f13[source]:
                status="unimplemented_enrichment"
                findings=["Prose/native glyphs are available where present, but required complete LaTeX reconstruction is disabled in this layout comparison; this is an unmet feature, not a formula-model accuracy score."]
            else:findings=["Complete selected source prose retained under original typography/line reflow rules, with required ordering and identifiers."]
            if source=="wikiskill" and number in {357,368}:
                findings=["Complete crosspage prose joined by same-version official assembly; one item with both original physical-page provenance fragments. No project continuation logic."]
            if source=="wikiskill" and number==362:findings.append("Bold lead-in and complete bootstrap opening1,000iterations retained; remaining source prose retained. Full protected positive still lacks required math delivery.")
            if source=="wikiskill" and number==363:findings.append("All winner/tie conditions and six source math meanings readable in native text; full protected positive lacks6inlineLaTeX spans.")
            if source=="seal" and number==30:findings.append("One logical paragraph spans p3/p4 with both provenance fragments; source content joins correctly, although F13 remains unimplemented.")
            if source=="seal" and number==21:findings.append("Knowledge Updating joins p2/p3 once, without custom continuation.")
            if source=="seal" and number==34:
                status="material";findings.append("Algorithm1 title is wrongly merged into the Unlike paragraph. S0 places body lines between prefix and suffix; S1 makes body a table, moves it before the entire main text. Heading separation remains incorrect.")
            if source=="seal" and number==51 and profile=="S1":
                status="material";findings.append("Equation4 is classified as a table; no empty formula item corresponding to S0's equation4. Required formula delivery unavailable in either arm.")
            if source=="dgm" and number==646:
                status="material";findings=["Source diff becomes one flattened code line, adds spaces inside strings/default keys and loses context indentation. Code enrichment is disabled; layout swap does not repair delivery."]
            if source=="dgm" and number in {650,652}:
                status="material";findings=["Prose words preserved, but quoted exact literals gain interior spaces (' edit ', ' old_str ', ' editor '), and wrap glyphs remain. Literal-preserving block delivery fails in both arms."]
            if source=="controls" and number in {12,13}:
                status="material";findings=["Comment and body flattened into one fenced code line; required six-line nesting lost in both arms; not a code-enrichment model evaluation."]
            if source=="controls" and number==14:
                status="material";findings=["S0 detaches inline items[i]<=limit into a standalone code block; S1 misclassifies it as formula and stock Markdown omits expression entirely. Inline source context not delivered."]
        boxes=[dict(item=t["self_ref"],**v) for t in matched for v in t.get("prov",[])]
        record=dict(profile=profile,unit_id=u["unit_id"],source=source,delivery_status=status,
            raw_source_fidelity_status=raw_status,findings=findings,F13_applicable=number in f13[source],
            F14_applicable=number in f14[source],matched_item_refs=[t["self_ref"] for t in matched],
            matched_text=[t["text"] for t in matched],output_provenance=boxes,
            expected_physical_pages=u["physical_pages_1based"],source_regions=u.get("scope_fragments",[]),
            localization_verdict="not_certified; explicit physical pages and boxes preserved for comparison; bounds alone do not prove source alignment")
        if source=="seal" and number==51 and profile=="S1":
            record["matched_table_refs"]=["#/tables/0"]
        records.append(record)
assert len(records)==123
assert all(len([r for r in records if r["profile"]==p])==41 for p in ["C1","S0","S1"])
assert len({(r["profile"],r["unit_id"]) for r in records})==123
summary={p:dict(collections.Counter(r["delivery_status"] for r in records if r["profile"]==p)) for p in ["C1","S0","S1"]}
# Evidence checks are guardrails on manual judgments, not string-based semantic grading.
assert "test_stats" in json.loads((HERE/"C1/dgm/page-51-vlm.json").read_text())["text"].replace("\\_","_")
assert "formula-not-decoded" in (HERE/"S1/controls/document.md").read_text()
assert all(len(json.loads((HERE/p/"wikiskill/document.json").read_text())["texts"][5]["prov"])==2 for p in ["S0","S1"])
save("unit-review.json",dict(method="Manual full-target source contract review; per-item mapping preserved. Disabled enrichment is separated from recognition quality. No output repairs, no model reruns, no unseen claims.",summary=summary,units=records))
print(json.dumps(summary,indent=2))

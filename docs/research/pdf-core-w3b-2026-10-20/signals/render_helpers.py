"""Static local-only Chrome rendering utility; never launched on import."""
from pathlib import Path
import html,json,subprocess
from lxml import etree
from character_helpers import mathml_visible,xml_entity_compat

def render_batch(items,workspace,tag="batch"):
    root=Path(workspace).resolve();work=root/"tmp"/("chrome-"+tag);work.mkdir(parents=True,exist_ok=True)
    for n in ["profile","disk-cache","crash"]:(work/n).mkdir(exist_ok=True)
    known=[];results=[]
    for i,it in enumerate(items):
        check=mathml_visible(it["mathml"])
        has_merror=set(check.get("unknown_tags",[]))=={"merror"} and "\\" not in check.get("visible_text","")
        if check["status"]!="KNOWN" and not has_merror:results.append({"unit_id":it["unit_id"],"status":"UNKNOWN","pass":None,"reason":check.get("reason"),"unknown_tags":check.get("unknown_tags",[])});continue
        tree=etree.fromstring(xml_entity_compat(it["mathml"]).encode(),parser=etree.XMLParser(resolve_entities=False,no_network=True))
        # Reject active/external content even for caller-supplied MathML.
        for node in tree.iter():
            for k in node.attrib:
                if k.lower().startswith("on") or k.lower().endswith("href") or k.lower()=="src":raise ValueError("active/external MathML attribute")
        known.append((it["unit_id"],etree.tostring(tree,encoding="unicode")))
    blocks="".join('<div class="unit" data-unit-id="'+html.escape(k,quote=True)+'"><math-display>'+m+'</math-display></div>' for k,m in known)
    script="""<script>window.addEventListener('load',()=>{const r=[...document.querySelectorAll('.unit')].map(e=>{let m=e.querySelector('math')||e.querySelector('math-display');let b=m.getBoundingClientRect();return {unit_id:e.dataset.unitId,bbox:{x:b.x,y:b.y,width:b.width,height:b.height},merror:!!e.querySelector('merror'),mathml_core_supported:CSS.supports('display','math'),renderstatus:b.width>0&&b.height>0&&!e.querySelector('merror')?'RENDERED_NONEMPTY':'UNKNOWN'};});document.getElementById('render-status').textContent=JSON.stringify(r);document.body.dataset.renderComplete='true';});</script>"""
    page='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'unsafe-inline\'"><style>body{font-size:20px;margin:20px;background:white;color:black}.unit{padding:20px;border-bottom:1px solid #bbb;min-height:70px;overflow:visible}math{font-family:serif}</style>'+blocks+'<pre id="render-status"></pre>'+script
    src=work/'static.html';src.write_text(page);shot=work/'render.png'
    cmd=['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless','--disable-gpu','--disable-background-networking','--disable-component-update','--no-first-run','--disable-sync','--disable-extensions','--disable-default-apps','--disable-crash-reporter','--disable-breakpad','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND','--user-data-dir='+str(work/'profile'),'--disk-cache-dir='+str(work/'disk-cache'),'--crash-dumps-dir='+str(work/'crash'),'--window-size=1500,'+str(min(16000,max(1200,180*len(known)))),'--virtual-time-budget=3000','--screenshot='+str(shot),'--dump-dom',src.as_uri()]
    try:proc=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as exc:
        results += [{"unit_id":k,"status":"UNKNOWN","pass":None,"reason":"renderer/environment failure: "+type(exc).__name__} for k,_ in known]
        return {"command":cmd,"returncode":None,"source_html":str(src),"results":results,"render_success_is_not_semantic_proof":True}
    (work/'stdout.html').write_text(proc.stdout);(work/'stderr.txt').write_text(proc.stderr)
    from lxml import html as lh
    dom=lh.fromstring(proc.stdout) if proc.stdout else None
    statuses=dom.xpath('//*[@id="render-status"]/text()') if dom is not None else []
    got=json.loads(statuses[0]) if statuses else []
    for r in got:
        r['pass']=False if r['merror'] and proc.returncode==0 else True if r['renderstatus']=='RENDERED_NONEMPTY' and r['mathml_core_supported'] and shot.exists() and proc.returncode==0 else None
        r['status']='KNOWN' if isinstance(r['pass'],bool) else 'UNKNOWN'
        r['reason']='actual MathML merror' if r['merror'] else 'actual nonempty Chrome render' if r['pass'] else 'renderer/environment/nonempty-bbox failure not established as input syntax error'
        r['screenshot']=str(shot);results.append(r)
    return {'command':cmd,'returncode':proc.returncode,'source_html':str(src),'results':results,'render_success_is_not_semantic_proof':True}

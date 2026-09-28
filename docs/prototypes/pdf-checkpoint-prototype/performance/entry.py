"""THROWAWAY timing entry: original adapter, optional sequential converter reuse."""
import time
BOOT=time.perf_counter()
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import experiment as exp
IMPORT_SECONDS=time.perf_counter()-BOOT
TIMES={}; SPANS=[]

def timed(owner,name,label):
    original=getattr(owner,name)
    def call(*args,**kwargs):
        start=time.perf_counter()
        try:return original(*args,**kwargs)
        finally:
            elapsed=time.perf_counter()-start
            TIMES[label]=TIMES.get(label,0)+elapsed
    setattr(owner,name,call)

from docling_core.types.doc import DoclingDocument
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
timed(DoclingDocument,'save_as_json','json_export_s')
timed(DoclingDocument,'export_to_markdown','markdown_export_s')
timed(DoclingParseDocumentBackend,'__init__','backend_constructor_s')
timed(exp,'method','method_fingerprint_s')
original_event=exp.event

def event(stage,pages,elapsed,**extra):
    end=time.perf_counter()
    SPANS.append({'stage':stage,'pages':pages,'start':end-elapsed,'end':end})
    return original_event(stage,pages,elapsed,**extra)
exp.event=event

args=sys.argv[1:]
daemon=args[0]=='--daemon'
session=args[0] in ('--session','--daemon')
requests=(json.loads(line) for line in sys.stdin) if daemon else (json.loads(Path(args[1]).read_text()) if session else [args])
if session:
    factory=exp.DocumentConverter
    cache={}
    def converter(**kwargs):
        option=next(iter(kwargs['format_options'].values()))
        key=(option.pipeline_cls.__name__,option.pipeline_options.model_dump_json(serialize_as_any=True))
        if key not in cache:cache[key]=factory(**kwargs)
        return cache[key]
    exp.DocumentConverter=converter
    instrument=exp.instrument
    initialized=False
    def once(forbid=False):
        global initialized
        assert not forbid, 'Warm restoration not part of this experiment; use fresh guarded restore'
        if not initialized:
            instrument(False); initialized=True
    exp.instrument=once

reports=[]
for index,argv in enumerate(requests):
    TIMES.clear(); SPANS.clear(); exp.EVENTS.clear()
    sys.argv=[str(ROOT/'experiment.py'),*argv]
    exp.START=time.perf_counter()
    exp.main()
    report={'index':index,'session':session,'module_import_once_s':IMPORT_SECONDS,
            'call_wall_s':time.perf_counter()-exp.START,'timing':dict(TIMES),'stage_spans':list(SPANS)}
    if session:
        report['pipeline_ids']=[id(v) for c in cache.values() for v in c.initialized_pipelines.values()]
    (exp.ARGS.out/'perf.json').write_text(json.dumps(report,indent=2))
    reports.append(report)
    if daemon: print('PERF_READY '+json.dumps({'out':str(exp.ARGS.out),'pipeline_ids':report['pipeline_ids']}),flush=True)
if session and not daemon:
    Path(args[1]).with_suffix('.report.json').write_text(json.dumps({'session_wall_s':time.perf_counter()-BOOT,'converter_instances':len(cache),'requests':reports},indent=2))

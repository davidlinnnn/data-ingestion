"""CT diagnostic: phase-boundary native thread creation; no engine mutation."""
exec(compile(open('/source/tests/pdf_processing/t09a_bounds/ocr-phase-probe/sitecustomize.py').read(), 'prior-observer', 'exec'))
if _directory and 'PDF_PROCESS_LIFECYCLE_FD' in os.environ:
    def snapshot(label):
        rows=[]
        for task in Path('/proc/self/task').iterdir():
            try:
                status=dict(line.split(':',1) for line in (task/'status').read_text().splitlines() if ':' in line)
                rows.append({'tid':int(task.name),'name':status['Name'].strip(),'nspid':status.get('NSpid','').strip()})
            except FileNotFoundError: pass
        status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
        row={'label':label,'time':time.time(),'pid':os.getpid(),'ppid':os.getppid(),'threads':rows,'rss_kb':int(status['VmRSS'].split()[0]),'affinity':sorted(os.sched_getaffinity(0))}
        with (Path(_directory).parent/'threads.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    prior_mark=_mark
    def _mark(stage):
        prior_mark(stage)
        snapshot(stage)
    prior_profile=_profile
    def _profile(frame,event,arg):
        prior_profile(frame,event,arg)
        if event in ('call','return') and frame.f_code.co_name=='__init__' and frame.f_code.co_filename.endswith('/onnxruntime/capi/onnxruntime_inference_collection.py'):
            instance=frame.f_locals.get('self')
            if instance is not None and type(instance).__name__=='InferenceSession':
                snapshot('ort_session_'+event)
    sys.setprofile(_profile)

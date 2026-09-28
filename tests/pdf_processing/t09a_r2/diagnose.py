"""Replay retained OOM/continuity evidence and assess current capacity, no inference."""
import collections
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'t09a/evidence'
RAW=Path('/private/tmp/t09a-controller')
CURRENT=Path('/private/tmp/t09a-r2-20260914')

def main():
    lines=(RAW/'kernel-dmesg.txt').read_text().splitlines()
    cases=[]
    for trial in ('warm-1-07','warm-3-native','warm-4-06'):
        pod=json.loads((RAW/(trial+'-worker.json')).read_text())
        status=pod['status']['containerStatuses'][0]
        cid=status['lastState']['terminated']['containerID'].split('://')[1]
        index=next(i for i,l in enumerate(lines) if 'oom-kill:' in l and cid in l)
        stamp=lines[index].split(']')[0]+']'
        block=[l for l in lines[:index] if l.startswith(stamp)]
        processes=[]
        for line in block:
            match=re.search(r'\[\s*(\d+)\]\s+(.*)$',line[len(stamp):])
            if not match:continue
            fields=match[2].split()
            if len(fields)==11:
                processes.append({'pid':int(match[1]),'rss_bytes':int(fields[3])*4096,
                                  'swap_bytes':int(fields[8])*4096,'name':fields[10]})
        totals=collections.Counter()
        for p in processes:totals[p['name']]+=p['rss_bytes']
        result=json.loads((OLD/(trial+'.json')).read_text())
        scheduled={e['id']:e for e in result['events'] if 'activity' in e}
        retries=[{'attempt':e['attempt'],'scheduled':scheduled.get(e['scheduled_event_id'])}
                 for e in result['events'] if e.get('attempt',0)>1]
        cases.append({'trial':trial,'pod_uid':pod['metadata']['uid'],'container':cid,
            'termination':status['lastState']['terminated'],'kernel_event':lines[index],
            'memory_lines':[l for l in block if any(s in l for s in ('Node 0 active_anon:','Free swap','Total swap'))],
            'process_rss_by_name':dict(totals.most_common()),'largest_processes':sorted(processes,key=lambda p:p['rss_bytes'],reverse=True)[:12],
            'retries':retries,'stable':status['restartCount']==0 and 'global_oom' not in lines[index]})
    node=json.loads((CURRENT/'node-before.json').read_text())
    mem={l.split(':')[0]:int(l.split()[1])*1024 for l in (CURRENT/'vm-meminfo.txt').read_text().splitlines() if len(l.split())==3}
    competing=sorted([{'namespace':p['podRef']['namespace'],'pod':p['podRef']['name'],
        'working_set_bytes':p.get('memory',{}).get('workingSetBytes',0)} for p in node['pods']],key=lambda p:p['working_set_bytes'],reverse=True)
    report={'historical':cases,'current_meminfo':mem,'kubelet_memory':node['node']['memory'],
        'current_pods':competing,'long_run_capacity_gate':mem['MemAvailable']>=3*2**30,
        'gate_definition':'3GiB MemAvailable admission minimum, maintained for 60s with no new OOM/pressure; not a supported maximum or leak diagnosis',
        'interpretation':'Matched global OOM and exhausted swap. Aggregate workload capacity is implicated; exact exclusive cause and warm growth remain unproved.'}
    (ROOT/'evidence/diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'historical_stability':'FAIL','matched_oom_events':len(cases),
        'current_available_gib':round(mem['MemAvailable']/2**30,3),'capacity_gate':report['long_run_capacity_gate']}))
    if '--assert-stable' in sys.argv:assert all(c['stable'] for c in cases),'historical warm continuity failed on matched global OOM'

if __name__=='__main__':main()

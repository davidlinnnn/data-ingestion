from pathlib import Path
import importlib.util
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('evaluation',P/'evaluate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
b,e=m.bins([{'label':'correct','p':1},{'label':'meaning_changed','p':0}],'p');assert e==0 and b[0]['n']==1 and b[9]['n']==1
b,e=m.bins([{'label':'meaning_changed','p':.8}],'p');assert e==.8
assert m.wilson(0,0) is None and m.wilson(0,10)[1]>0
rs=[{'state':'OK','label':'meaning_changed','gate_state':'verified','raw_safe':.9,'calibrated_safe':.95,'seconds':1,'split_group':'a'},{'state':'FAILED','label':'correct','gate_state':'failed','raw_safe':None,'calibrated_safe':None,'split_group':'b'}]
r=m.summarize(rs);assert r['verified']==1 and r['verified_error_rate']==1 and r['coverage']==.5 and r['failed_or_NOT_RUN']==1
print('4 evaluation accounting controls passed; no model output opened')

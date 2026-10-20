import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('metrics',P/'metrics.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert m.auc([0,1],[0,1])==1
assert m.auc([0,1],[1,0])==0
assert m.auc([0,1],[.5,.5])==.5
assert m.auc([1,1],[.2,.8]) is None
b,e=m.binned([{'p_faithful':1,'label':'correct'},{'p_faithful':0,'label':'meaning_changed'}]);assert e==0 and b[9]['count']==1 and b[0]['count']==1
b,e=m.binned([{'p_faithful':.8,'label':'meaning_changed'}]);assert e==.8
r=m.calculate([{'state':'OK','label':'meaning_changed','p_faithful':.8,'p_changed':.1,'gate_state':'verified','seconds':1,'split_group':'a'},{'state':'FAILED','label':'correct','gate_state':'failed','split_group':'b'}]);assert r['verified']==1 and r['verified_changed']==1 and r['verified_error_rate']==1 and r['verified_coverage']==.5
assert len(r['threshold_curve'])==21 and r['threshold_curve'][16]['threshold']==.8
assert m.wilson(0,0) is None and m.wilson(0,10)[1]>0
print('9 metric controls passed; no model outputs read')

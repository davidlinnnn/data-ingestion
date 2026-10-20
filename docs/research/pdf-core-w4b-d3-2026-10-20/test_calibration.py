from pathlib import Path
import importlib.util
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('cal',P/'calibrate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert m.auc([0,1],[0,1])==1 and m.auc([0,1],[1,0])==0
assert m.auc([0,1],[.5,.5])==.5 and m.auc([1,1],[.1,.9]) is None
c=m.fit([.1,.2,.8,.9],[0,0,1,1]);assert c['state']=='FIT' and c['a']>=0 and m.apply(c,.9)>m.apply(c,.1)
assert m.fit([.4,.6],[1,1])['state']=='UNFITTABLE_SINGLE_CLASS'
g=m.threshold([.1,.8,.9],[0,1,1]);assert g['threshold']==.8 and g['dev_verified']==2 and g['dev_error_rate']==0
assert m.threshold([.9,.8],[0,1])['threshold'] is None
# Boundary inclusion and all-equal score ties cannot falsely manufacture a zero-error subset.
assert m.threshold([.8,.8],[1,0])['threshold'] is None
assert m.threshold([.8,.8],[1,1])['dev_verified']==2
print('8 calibration/selection controls passed; no model or test output opened')

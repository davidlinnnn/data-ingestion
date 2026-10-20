from pathlib import Path
import sys,os,json
P=Path(__file__).resolve().parent;ROOT=Path.cwd()
sys.path.insert(0,str(ROOT/'docs/research/pdf-core-w4-decision-gate-2026-10-20/plot-libs'));os.environ['MPLCONFIGDIR']=str(P/'plot-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
cats=['formula','code','caption','description','chart'];models=['d3-nano','d3-mini'];colors=['#177e89','#b74d35']
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
for ax,cat in zip(axes.flat,cats):
 ax.plot([0,1],[0,1],color='gray',ls='--',lw=1)
 for model,color in zip(models,colors):
  path=P/'evaluation'/model/'metrics.json'
  if not path.exists():continue
  m=json.loads(path.read_text())['categories'][cat]
  for key,style,name in [('reliability_before','--','raw'),('reliability_after','-','Platt')]:
   bins=[b for b in m[key] if b['n']]
   if not bins:continue
   ax.plot([b['mean_probability'] for b in bins],[b['meaning_preserved'] for b in bins],style,color=color,marker='o',ms=4,label=f'{model} {name}')
 ax.set(title=cat,xlim=(-.03,1.03),ylim=(-.03,1.03),xlabel='Predicted meaning-preserved probability',ylabel='Observed correct + minor fraction');ax.grid(alpha=.2)
axes.flat[-1].axis('off');h,l=axes.flat[0].get_legend_handles_labels();axes.flat[-1].legend(h,l,loc='upper left');axes.flat[-1].text(.02,.55,'Test only;10 fixed equal-width bins.\nNo post-test fitting or threshold selection.\nCaption/chart: no dev negatives, Platt not fitted.\nPoints share source pages; not iid production risk.\nQ1=P(faithful), Q2=P(yes).',va='top',fontsize=11)
fig.suptitle('Decision3.0: frozen DEV calibration evaluated on TEST',fontsize=16)
fig.savefig(P/'reliability-comparison.png',dpi=180);fig.savefig(P/'reliability-comparison.svg');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
for model,color in zip(models,colors):
 path=P/'evaluation'/model/'metrics.json'
 if not path.exists():continue
 d=json.loads(path.read_text())['categories']
 x=[d[c]['coverage'] for c in cats if d[c]['verified']];y=[d[c]['verified_error_rate'] for c in cats if d[c]['verified']];names=[c+' (v='+str(d[c]['verified'])+', e='+str(d[c]['verified_changed'])+')' for c in cats if d[c]['verified']]
 axes[0].scatter(x,y,label=model,color=color)
 for a,b,c in zip(x,y,names):axes[0].annotate(c,(a,b),xytext=((-145,5) if model=='d3-nano' and c.startswith('code') else (8,12) if model=='d3-mini' and c.startswith('description') else (8,4)),textcoords='offset points',fontsize=9)
 axes[1].plot(cats,[d[c]['latency_seconds']['median'] for c in cats],marker='o',color=color,label=model)
axes[0].axhline(.02,color='gray',ls='--',label='2% DEV selection target, not TEST guarantee');axes[0].set(xlim=(0,1),ylim=(0,1.05),xlabel='Verified TEST coverage',ylabel='Changed meaning / verified',title='One frozen DEV operating point per category');axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
axes[1].set(ylabel='Single-judgement median seconds',title='Local MPS end-to-end system_one');axes[1].legend();axes[1].grid(alpha=.2)
fig.savefig(P/'quality-cost.png',dpi=180);fig.savefig(P/'quality-cost.svg');plt.close(fig)
print('Plots exported')

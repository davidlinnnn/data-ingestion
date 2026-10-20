from pathlib import Path
import sys,os,json,csv
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'plot-libs'));os.environ['MPLCONFIGDIR']=str(P/'plot-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=json.loads((P/'test-metrics.json').read_text())['categories']
fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
for ax,(cat,d) in zip(axes.flat,D.items()):
    bins=[b for b in d['reliability'] if b['count']]
    x=[b['mean_confidence'] for b in bins];y=[b['acceptable_fraction'] for b in bins]
    ax.plot([0,1],[0,1],color='gray',ls='--',lw=1)
    ax.scatter(x,y,s=[25+b['count']*6 for b in bins],color='#136f63',alpha=.8)
    for b in bins:ax.annotate(str(b['count']),(b['mean_confidence'],b['acceptable_fraction']),xytext=(3,5),textcoords='offset points',fontsize=8)
    ax.set(xlim=(-.03,1.03),ylim=(-.03,1.08),title=f"{cat}: n={d['eligible_test']}, ECE={d['ECE']:.3f}",xlabel='Mean P(faithful)',ylabel='Observed meaning preserved (correct + minor)');ax.grid(alpha=.2)
axes.flat[-1].axis('off');axes.flat[-1].text(.02,.9,'Test only; 10 fixed equal-width bins\nLabels = bin counts; size scales with count.\nNo fitted calibration or test threshold selection.\nRepeated chart points share source images.\nNo source errors in caption test: rejection untested.\nFormula: 2/55 inputs have numeric locator hints.',va='top',fontsize=11)
fig.suptitle('VJev-Vision on document enrichment: reliability',fontsize=16)
fig.savefig(P/'reliability.png',dpi=180);fig.savefig(P/'reliability.svg');plt.close(fig)
fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
for ax,(cat,d) in zip(axes.flat,D.items()):
    curve=d['threshold_curve'];ax.plot([r['threshold'] for r in curve],[r['coverage'] for r in curve],label='Verified coverage',color='#136f63')
    ax.plot([r['threshold'] for r in curve],[float('nan') if r['error_rate'] is None else r['error_rate'] for r in curve],label='Changed meaning / verified',color='#b33b35',marker='.',ms=4)
    ax.axvline(.8,color='gray',ls='--',lw=1);ax.set(xlim=(0,1),ylim=(-.03,1.03),title=cat,xlabel='Fixed P(faithful) threshold',ylabel='Fraction');ax.grid(alpha=.2)
axes.flat[-1].axis('off');h,l=axes.flat[0].get_legend_handles_labels();axes.flat[-1].legend(h,l,loc='upper left');axes.flat[-1].text(.02,.60,'0.8 was fixed before model outputs.\nCurves shown for reference, not optimization.\nUndefined rates (zero verified) are omitted.\nFinite, clustered test set; not production risk.\nFormula includes 2 numeric locator hints.',va='top',fontsize=11)
fig.suptitle('VJev-Vision: complete predeclared threshold curves',fontsize=16)
fig.savefig(P/'threshold-curves.png',dpi=180);fig.savefig(P/'threshold-curves.svg');plt.close(fig)
with (P/'threshold-curves.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=['category','threshold','verified','meaning_changed','error_rate','coverage']);w.writeheader()
    for cat,d in D.items():
        for r in d['threshold_curve']:w.writerow({'category':cat,**{k:r[k] for k in w.fieldnames if k!='category'}})
print('Standalone reliability/threshold SVG+PNG and full21-threshold CSV written')

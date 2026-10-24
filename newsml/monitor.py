"""Batch covariate and prediction drift; no claim of performance drift without labels."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp
from .core import text_input, write_json, load_bundle

def drift_report(bundle,reference,current):
    def texts(df):
        if 'title' not in df:raise ValueError('CSV requires title')
        desc=df['description'].fillna('') if 'description' in df else ['']*len(df)
        return [text_input(t,d) for t,d in zip(df.title,desc)]
    a,b=texts(reference),texts(current)
    if len(a)<20 or len(b)<20:raise ValueError('At least 20 records per drift window required')
    pipe=bundle['pipeline'];vec=pipe.named_steps['tfidf'];analyzer=vec.build_analyzer();vocab=vec.vocabulary_
    def oov(items):
        out=[]
        for s in items:
            terms=analyzer(s);out.append(sum(t not in vocab for t in terms)/max(1,len(terms)))
        return float(np.mean(out))
    al=[len(t.split()) for t in a];bl=[len(t.split()) for t in b];ks=ks_2samp(al,bl)
    pa=pipe.predict(a);pb=pipe.predict(b)
    da=np.array([(pa==c).mean() for c in pipe.classes_]);db=np.array([(pb==c).mean() for c in pipe.classes_])
    oa,ob=oov(a),oov(b);js=float(jensenshannon(da+1e-9,db+1e-9,base=2))
    alerts=[]
    if ks.statistic>.20 and ks.pvalue<.01:alerts.append('text_length_shift')
    if ob-oa>.15:alerts.append('vocabulary_coverage_drop')
    if js>.15:alerts.append('prediction_distribution_shift')
    return {'model_version':bundle['run_id'],'reference_rows':len(a),'current_rows':len(b),'length_ks_statistic':float(ks.statistic),'length_ks_pvalue':float(ks.pvalue),'reference_mean_words':float(np.mean(al)),'current_mean_words':float(np.mean(bl)),'reference_oov_fraction':oa,'current_oov_fraction':ob,'prediction_js_distance':js,'reference_prediction_distribution':dict(zip(map(str,pipe.classes_),map(float,da))),'current_prediction_distribution':dict(zip(map(str,pipe.classes_),map(float,db))),'alerts':alerts,'thresholds':{'length_ks':.20,'length_p':.01,'oov_increase':.15,'js_distance':.15},'interpretation':'Heuristic alerts for investigation. Drift does not prove accuracy degradation.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--artifacts',default='artifacts');p.add_argument('--output',default='artifacts/latest_drift.json');a=p.parse_args()
    bundle,run=load_bundle(a.artifacts)
    report=drift_report(bundle,pd.read_csv(run/'reference.csv'),pd.read_csv(a.input));write_json(a.output,report);print(report)

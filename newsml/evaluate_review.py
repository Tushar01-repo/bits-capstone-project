"""Evaluate only the reserved, independently reviewed sample."""
import argparse
import json
import pandas as pd
from .core import LABELS,load_bundle,write_json
from .pipeline import scores

def evaluate(path,artifacts,output):
    bundle,run=load_bundle(artifacts);df=pd.read_csv(path).fillna('')
    required={'group_id','human_label','reviewer','rationale'}
    if not required.issubset(df):raise ValueError('Use the generated human_review_template.csv')
    if df.empty or df.group_id.duplicated().any():raise ValueError('Review must contain unique records')
    if not df.human_label.isin(LABELS).all() or not df.reviewer.str.strip().ne('').all() or not df.rationale.str.strip().ne('').all():raise ValueError('Every row needs a valid human_label, reviewer and rationale')
    reserved=pd.read_csv(run/'human_review_template.csv').fillna('')
    if not set(df.group_id).issubset(set(reserved.group_id)):raise ValueError('Rows must belong to reserved review sample')
    # Use immutable original text, not possibly edited annotation text.
    joined=df[['group_id','human_label','reviewer','rationale']].merge(reserved[['group_id','title','description']],on='group_id',validate='one_to_one')
    texts=joined.title+' '+joined.description
    model=bundle['pipeline'];report=scores(joined.human_label,model.predict(texts),model.predict_proba(texts))
    report.update(model_version=bundle['run_id'],rows=len(df),label_provenance='User-supplied human review; reviewer identities not independently verified')
    write_json(output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--artifacts',default='artifacts');p.add_argument('--output',default='artifacts/human_evaluation.json');a=p.parse_args();print(evaluate(a.input,a.artifacts,a.output))

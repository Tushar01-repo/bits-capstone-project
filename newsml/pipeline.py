"""Offline preparation, chronological evaluation and versioned artifact production."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import uuid
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score, log_loss
from .core import LABELS, normalize, text_input, sha256, write_json, predict
from .monitor import drift_report

REQUIRED = {'title','description','published_at','sentiment_cat','url','source','topic'}

def prepare(path):
    df = pd.read_csv(path)
    missing = REQUIRED - set(df)
    if missing: raise ValueError(f'Missing required columns: {sorted(missing)}')
    report = {'raw_rows':len(df), 'missing_descriptions':int(df.description.isna().sum()),
              'raw_labels':df.sentiment_cat.value_counts().to_dict()}
    df['title'] = df.title.fillna('').astype(str).str.strip()
    df['description'] = df.description.fillna('').astype(str).str.strip()
    df['sentiment_cat'] = df.sentiment_cat.fillna('').astype(str).str.lower().str.strip()
    df['published_at'] = pd.to_datetime(df.published_at, errors='coerce', utc=True)
    df['group_id'] = df.title.map(normalize).map(lambda s:hashlib.sha256(s.encode()).hexdigest())
    seed = df.url.fillna('').str.contains('seed-corpus.local',regex=False)
    removed = df.title.str.lower().isin(['[removed]','removed',''])
    invalid = df.published_at.isna() | ~df.sentiment_cat.isin(LABELS)
    report.update(seed_rows=int(seed.sum()), removed_or_empty_titles=int(removed.sum()),invalid_rows=int(invalid.sum()))
    rejected = df[seed | removed | invalid].copy()
    rejected['rejection_reason'] = [';'.join(name for name,mask in [('seed_url',seed),('empty_or_removed',removed),('invalid_date_or_label',invalid)] if mask.loc[i]) for i in rejected.index]
    df = df[~(seed | removed | invalid)].sort_values('published_at',kind='stable').copy()
    # Conservative title-level grouping avoids leakage across recurring or syndicated titles.
    dup = df.duplicated('group_id',keep='first')
    report['duplicate_title_rows_removed'] = int(dup.sum())
    duplicates = df[dup].copy()
    df = df[~dup].copy()
    df['text'] = [text_input(t,d) for t,d in zip(df.title,df.description)]
    report['clean_rows'] = len(df)
    report['policy'] = 'Keep earliest normalized-title occurrence. May remove different stories sharing a generic title. No automatic language exclusion.'
    if len(df) < 60: raise ValueError('At least 60 clean rows required for this pipeline')
    if set(df.sentiment_cat) != set(LABELS): raise ValueError('All three sentiment classes required')
    return df, rejected, duplicates, report

def split_data(df, review_size=300):
    # Hold out a deterministic sample for future independent human evaluation.
    review_size = min(review_size, max(0,len(df)//10))
    review = df.sample(n=review_size,random_state=42)
    remaining = df.drop(review.index).sort_values('published_at',kind='stable')
    dates = remaining.published_at.dt.strftime('%Y-%m-%d')
    unique_dates = sorted(dates.unique())
    if len(unique_dates)<5: raise ValueError('At least five distinct publication dates required')
    # Split only at day boundaries; no day is shared between chronological partitions.
    counts = dates.value_counts().sort_index().cumsum()
    cut1 = counts.index[min(int(np.searchsorted(counts.values,len(remaining)*.70)),len(counts)-3)]
    cut2 = counts.index[min(max(int(np.searchsorted(counts.values,len(remaining)*.85)),list(counts.index).index(cut1)+1),len(counts)-2)]
    train = remaining[dates<=cut1]; val = remaining[(dates>cut1)&(dates<=cut2)]; test = remaining[dates>cut2]
    for name, frame in [('train',train),('validation',val),('test',test)]:
        if set(frame.sentiment_cat)!=set(LABELS): raise ValueError(f'{name} lacks a class; supply more representative dated data')
    return train,val,test,review

def scores(y,p,prob=None):
    out={'accuracy':float(accuracy_score(y,p)), 'macro_f1':float(f1_score(y,p,labels=LABELS,average='macro',zero_division=0)),
         'classification_report':classification_report(y,p,labels=LABELS,output_dict=True,zero_division=0),
         'confusion_matrix':confusion_matrix(y,p,labels=LABELS).tolist(),'label_order':LABELS}
    if prob is not None: out['log_loss']=float(log_loss(y,prob,labels=LABELS))
    return out

def run_pipeline(input_path, output='artifacts', review_size=300):
    root=Path(output); root.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    run=root/run_id; run.mkdir()
    def log(event,**values):
        record={'time':datetime.now(timezone.utc).isoformat(),'event':event,**values}
        with (run/'execution.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        print(json.dumps(record),flush=True)
    log('started',run_id=run_id,input_sha256=sha256(input_path))
    df,rejected,duplicates,quality=prepare(input_path)
    train,val,test,review=split_data(df,review_size)
    quality['splits']={k:{'rows':len(v),'labels':v.sentiment_cat.value_counts().to_dict(),'start':str(v.published_at.min()),'end':str(v.published_at.max())} for k,v in [('train',train),('validation',val),('test',test),('reserved_review',review)]}
    write_json(run/'data_quality.json',quality)
    rejected.to_csv(run/'rejected.csv',index=False);duplicates.to_csv(run/'duplicates.csv',index=False)
    for name,frame in [('train',train),('validation',val),('test',test)]:frame.to_csv(run/f'{name}.csv',index=False)
    # Blind template: existing automated labels are intentionally excluded.
    template=review[['group_id','published_at','title','description','source','topic']].copy()
    for c in ['human_label','reviewer','rationale']:template[c]=''
    template.to_csv(run/'human_review_template.csv',index=False)
    write_json(run/'reserved_review_ids.json',review.group_id.tolist())
    log('prepared',**quality['splits'])
    candidates=[];best=None;best_score=-1
    for c in [.5,2.0]:
        model=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),min_df=2,max_df=.98,max_features=40000,sublinear_tf=True)),
                        ('classifier',LogisticRegression(C=c,class_weight='balanced',max_iter=1000,random_state=42))])
        model.fit(train.text,train.sentiment_cat)
        score=f1_score(val.sentiment_cat,model.predict(val.text),average='macro')
        candidates.append({'C':c,'validation_macro_f1':float(score)})
        log('candidate_trained',**candidates[-1])
        if score>best_score:best,best_score=model,score
    # Freeze selected model trained only on train. Test data never tunes parameters.
    majority=str(train.sentiment_cat.mode().iloc[0]);prob=best.predict_proba(test.text);pred=best.classes_[prob.argmax(axis=1)]
    metrics={'label_provenance':'Automated dataset labels; not independently verified financial sentiment.',
             'validation_candidates':candidates,'selected_C':best.named_steps['classifier'].C,
             'test':scores(test.sentiment_cat,pred,prob),'majority_baseline':scores(test.sentiment_cat,[majority]*len(test)),
             'human_evaluation':{'status':'pending_human_review','reserved_rows':len(review)}}
    write_json(run/'metrics.json',metrics)
    bundle={'pipeline':best,'run_id':run_id,'review_threshold':.60,'label_provenance':metrics['label_provenance']}
    joblib.dump(bundle,run/'model.joblib',compress=3)
    batch=test[['group_id','published_at','title','sentiment_cat','source','topic']].copy()
    batch['prediction']=pred;batch['confidence']=prob.max(axis=1);batch.to_csv(run/'test_predictions.csv',index=False)
    slices=[]
    for col in ['topic','source']:
        for name,part in batch.groupby(col):
            if len(part)>=30:slices.append({'dimension':col,'value':str(name),'n':len(part),'accuracy':float(accuracy_score(part.sentiment_cat,part.prediction)), 'macro_f1':float(f1_score(part.sentiment_cat,part.prediction,labels=LABELS,average='macro',zero_division=0))})
    examples=test.head(8)[['title','description']].to_dict('records')
    rai={'limitations':['Labels were generated automatically; high agreement is not proof of financial accuracy.','Source/topic slices are error analysis, not demographic fairness certification.','Snippets omit context; company-targeted sentiment and events are not supported.','Probabilities are uncalibrated; 0.60 review cutoff is an operational heuristic.','No stock price prediction or investment recommendation.'], 'slices':slices,'explanations':[{'input':r,'output':p} for r,p in zip(examples,predict(bundle,examples,True))]}
    write_json(run/'responsible_ai.json',rai)
    reference=train[['title','description']].sample(n=min(2000,len(train)),random_state=42)
    reference.to_csv(run/'reference.csv',index=False)
    drift=drift_report(bundle,reference,test[['title','description']]);write_json(run/'drift.json',drift)
    shifted=pd.DataFrame({'title':['Football tournament match score']*200,'description':['Players scored goals in the stadium. ' * 30]*200})
    demo=drift_report(bundle,reference,shifted);demo['scenario']='Synthetic sports/length shift for monitoring demonstration, not real production data.'
    write_json(run/'drift_simulation.json',demo)
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit='not_in_git'
    write_json(run/'manifest.json',{'run_id':run_id,'git_commit':commit,'input_sha256':sha256(input_path),'python':platform.python_version(),'sklearn':sklearn.__version__,'pandas':pd.__version__,'numpy':np.__version__,'random_seed':42,'model_sha256':sha256(run/'model.joblib'),'completed_at':datetime.now(timezone.utc).isoformat()})
    # Promotion occurs only after all artifacts exist. Atomic replace avoids partial pointer writes.
    write_json(root/'current.tmp',{'run_id':run_id,'model_sha256':sha256(run/'model.joblib')})
    (root/'current.tmp').replace(root/'current.json')
    log('completed',test_macro_f1=metrics['test']['macro_f1'],test_accuracy=metrics['test']['accuracy'])
    return run

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/raw/news_sentiment_raw.csv');p.add_argument('--output',default='artifacts');p.add_argument('--review-size',type=int,default=300)
    a=p.parse_args();run_pipeline(a.input,a.output,a.review_size)

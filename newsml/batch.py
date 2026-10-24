import argparse
from pathlib import Path
import pandas as pd
from .core import load_bundle,predict

def batch(input_path,output_path,artifacts='artifacts'):
    df=pd.read_csv(input_path)
    if 'title' not in df:raise ValueError('CSV requires title')
    if 'description' not in df:df['description']=''
    if df.empty:raise ValueError('CSV has no records')
    bundle,_=load_bundle(artifacts);results=[]
    records=df[['title','description']].fillna('').to_dict('records')
    for i in range(0,len(records),500):results.extend(predict(bundle,records[i:i+500]))
    for c in ['sentiment','confidence','needs_review','model_version']:df['predicted_'+c]=[r[c] for r in results]
    for c in bundle['pipeline'].classes_:df['probability_'+c]=[r['probabilities'][c] for r in results]
    Path(output_path).parent.mkdir(parents=True,exist_ok=True);df.to_csv(output_path,index=False)
    return len(df)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--artifacts',default='artifacts');a=p.parse_args();print({'predicted_rows':batch(a.input,a.output,a.artifacts)})

"""Integration checks use synthetic data only for software correctness, never quality claims."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
import pandas as pd
from newsml.core import load_bundle,predict,text_input
from newsml.pipeline import prepare,split_data,run_pipeline
from newsml.batch import batch
from newsml.monitor import drift_report
from newsml.server import make_server
from newsml.evaluate_review import evaluate

class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.raw=cls.root/'fixture.csv';cls.art=cls.root/'artifacts'
        rows=[]
        phrases={'positive':'strong growth profits improve success','negative':'loss decline weak failure costs','neutral':'scheduled meeting announcement report date'}
        for day in range(60):
            for j,(label,phrase) in enumerate(phrases.items()):
                rows.append({'title':f'{phrase} bulletin {day} {j}','description':phrase+' company statement', 'published_at':str(pd.Timestamp('2025-01-01',tz='UTC')+pd.Timedelta(days=day)),'sentiment_cat':label,'url':f'https://example.invalid/{day}/{j}','source':'synthetic fixture','topic':'test','compound':j})
        pd.DataFrame(rows).to_csv(cls.raw,index=False)
        with contextlib.redirect_stdout(io.StringIO()):cls.run_dir=run_pipeline(cls.raw,cls.art,12)
        cls.bundle,_=load_bundle(cls.art)
        cls.server=make_server('127.0.0.1',0,str(cls.art),str(cls.root/'logs'));cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def test_chronology_and_disjoint_groups(self):
        df,*_=prepare(self.raw);train,val,test,review=split_data(df,12)
        self.assertLess(train.published_at.max(),val.published_at.min());self.assertLess(val.published_at.max(),test.published_at.min())
        parts=[set(p.group_id) for p in [train,val,test,review]]
        for i,a in enumerate(parts):
            for b in parts[i+1:]:self.assertFalse(a & b)
    def test_normalized_duplicate_removed(self):
        df=pd.read_csv(self.raw);dup=df.iloc[[0]].copy();dup['title']='  '+dup.title.str.upper()+'!!!';path=self.root/'dupes.csv';pd.concat([df,dup]).to_csv(path,index=False)
        clean,_,duplicates,report=prepare(path);self.assertEqual(len(clean),len(df));self.assertEqual(len(duplicates),1)
    def test_invalid_schema_fails(self):
        p=self.root/'invalid.csv';pd.DataFrame({'title':['one']}).to_csv(p,index=False)
        with self.assertRaises(ValueError):prepare(p)
    def test_no_score_leakage(self):
        a={'title':'Company reports losses','description':'Earnings declined','compound':1,'pos':1}
        b={**a,'compound':-1,'pos':0,'sentiment_cat':'positive'}
        self.assertEqual(predict(self.bundle,[a]),predict(self.bundle,[b]))
    def test_validation_and_probabilities(self):
        for title in ['',None,123]:
            with self.assertRaises(ValueError):text_input(title)
        with self.assertRaises(ValueError):predict(self.bundle,[{'title':'a'}]*501)
        p=predict(self.bundle,[{'title':'Profits grow strongly'}])[0];self.assertAlmostEqual(sum(p['probabilities'].values()),1)
    def test_explanation_contributions_match_logit(self):
        m=self.bundle['pipeline'];text=text_input('strong growth profits improve success');x=m.named_steps['tfidf'].transform([text]);k=int(m.predict_proba([text])[0].argmax())
        expected=float((x @ m.named_steps['classifier'].coef_[k] + m.named_steps['classifier'].intercept_[k]).item());actual=float(m.decision_function([text])[0,k]);self.assertAlmostEqual(expected,actual)
    def test_batch_matches_direct(self):
        p=self.root/'batch.csv';out=self.root/'output.csv';pd.DataFrame({'title':['profits improve','loss decline']}).to_csv(p,index=False);self.assertEqual(batch(p,out,self.art),2)
        actual=pd.read_csv(out).predicted_sentiment.tolist();expected=[r['sentiment'] for r in predict(self.bundle,[{'title':'profits improve'},{'title':'loss decline'}])];self.assertEqual(actual,expected)
    def test_drift_identity_and_shift(self):
        ref=pd.read_csv(self.run_dir/'reference.csv');same=drift_report(self.bundle,ref,ref);self.assertEqual(same['alerts'],[])
        shifted=pd.DataFrame({'title':['football sports stadium']*30,'description':['goal '*100]*30});self.assertTrue(drift_report(self.bundle,ref,shifted)['alerts'])
    def test_api_dashboard_and_metrics(self):
        for route in ['/','/health','/report/metrics','/report/drift','/report/responsible-ai','/metrics']:
            with urlopen(self.base+route) as r:self.assertEqual(r.status,200)
        req=Request(self.base+'/predict',data=json.dumps({'title':'profits improve'}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:self.assertIn('explanation',json.load(r))
        req=Request(self.base+'/batch',data=b'title,description\nprofits improve,growth\nloss falls,weak\n',headers={'Content-Type':'text/csv'})
        with urlopen(req) as r:self.assertEqual(json.load(r)['count'],2)
    def test_api_rejects_bad_requests(self):
        cases=[('/predict',b'{','application/json'),('/predict',b'{"title":""}','application/json'),('/batch',b'wrong\nhello\n','text/csv')]
        for path,data,ctype in cases:
            with self.assertRaises(HTTPError) as ctx:urlopen(Request(self.base+path,data=data,headers={'Content-Type':ctype}))
            self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:urlopen(Request(self.base+'/predict',data=b'x',headers={'Content-Type':'application/json','Content-Length':'2000001'}))
        self.assertEqual(ctx.exception.code,413)
    def test_unreviewed_labels_rejected(self):
        with self.assertRaises(ValueError):evaluate(self.run_dir/'human_review_template.csv',self.art,self.root/'human.json')
    def test_artifact_manifest(self):
        manifest=json.loads((self.run_dir/'manifest.json').read_text());self.assertEqual(manifest['run_id'],self.bundle['run_id']);self.assertEqual(len(manifest['input_sha256']),64)

    def csv_request(self,route,frame):
        body=frame.to_csv(index=False).encode('utf-8-sig')
        req=Request(self.base+route,data=body,headers={'Content-Type':'text/csv'})
        with urlopen(req) as r:return json.load(r)
    def test_uploaded_evaluation_known_scores(self):
        frame=pd.DataFrame({'title':['strong profit growth','weak losses failure','scheduled announcement date']})
        expected=[r['sentiment'] for r in predict(self.bundle,frame.to_dict('records'))]
        frame['sentiment']=expected
        frame.loc[2,'sentiment']=next(c for c in ['positive','negative','neutral'] if c!=expected[2])
        d=self.csv_request('/evaluate',frame)
        self.assertAlmostEqual(d['accuracy'],2/3);self.assertEqual(d['incorrect_rows'],1)
        self.assertEqual(sum(map(sum,d['confusion_matrix'])),3)
        self.assertEqual(d['model_version'],self.bundle['run_id'])
        self.assertTrue(d['warnings']);self.assertEqual(len(d['predictions']),3)
    def test_upload_validation(self):
        invalid=[pd.DataFrame({'title':['hello']}),pd.DataFrame({'title':['hello'],'sentiment':['mixed']}),pd.DataFrame({'title':[''],'sentiment':['positive']}),pd.DataFrame({'title':['hello'],'sentiment':['positive'],'label':['negative']})]
        for frame in invalid:
            with self.assertRaises(HTTPError) as err:self.csv_request('/evaluate',frame)
            self.assertEqual(err.exception.code,400)
        with self.assertRaises(HTTPError) as err:self.csv_request('/drift',pd.DataFrame({'title':['a']*19}))
        self.assertEqual(err.exception.code,400)
        with self.assertRaises(HTTPError) as err:self.csv_request('/evaluate',pd.DataFrame({'title':['a']*501,'sentiment':['neutral']*501}))
        self.assertEqual(err.exception.code,400)
    def test_evaluation_overlap_and_alias(self):
        frame=pd.read_csv(self.run_dir/'train.csv').head(3)[['title','description','sentiment_cat']]
        d=self.csv_request('/evaluate',frame)
        self.assertEqual(d['training_title_overlap_rows'],3)
        self.assertEqual(d['label_column'],'sentiment_cat')
    def test_live_drift_and_operation_counts(self):
        ref=pd.read_csv(self.run_dir/'reference.csv')
        before=(self.art/'current.json').read_bytes()
        d=self.csv_request('/drift',ref[['title','description']])
        self.assertEqual(d['alerts'],[])
        shifted=pd.DataFrame({'title':[f'Sports championship fixture {i}' for i in range(30)],'description':['football stadium goals '*100]*30})
        self.assertTrue(self.csv_request('/drift',shifted)['alerts'])
        self.assertEqual(before,(self.art/'current.json').read_bytes())
        with urlopen(self.base+'/monitoring') as response:m=json.load(response)
        self.assertGreaterEqual(m['operations']['/drift'],2)

if __name__=='__main__':unittest.main()

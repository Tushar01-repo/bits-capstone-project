"""Rebuild model, reports and batch output; run HTTP smoke checks; record evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
from urllib.request import Request,urlopen
from newsml.pipeline import run_pipeline
from newsml.batch import batch
from newsml.core import write_json
from newsml.server import make_server

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/raw/news_sentiment_raw.csv');p.add_argument('--output',default='artifacts');a=p.parse_args()
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],check=True)
    run=run_pipeline(a.input,a.output)
    count=batch(run/'test.csv',run/'batch_predictions.csv',a.output)
    server=make_server('127.0.0.1',0,a.output,str(run/'smoke_logs'));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/health') as r:health=json.load(r)
        req=Request(base+'/predict',data=json.dumps({'title':'Company reports a quarterly loss','description':'Revenue declined and operating costs rose.'}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:prediction=json.load(r)
        with urlopen(base+'/') as r:dashboard_ok=r.status==200 and b'News Signal' in r.read()
        write_json(run/'golden_path.json',{'status':'passed','unit_integration_tests':'passed','batch_rows':count,'http_health':health,'http_prediction':prediction,'dashboard_http_check':dashboard_ok,'external_steps_not_run':['GitHub-hosted workflow','Docker image build and Compose deployment','Human review','Screen recording']})
    finally:server.shutdown();server.server_close();thread.join()
    print(f'Golden path complete: {run}\nStart dashboard: python -m newsml.server')

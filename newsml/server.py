"""Bounded local demonstration HTTP API. Use private networking/TLS proxy for hosting."""
import argparse
import csv
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import threading
import time
import uuid
from .core import load_bundle,predict

MAX_BODY=2_000_000

class State:
    def __init__(self,artifacts,logs):
        self.bundle,self.run=load_bundle(artifacts);self.logs=Path(logs);self.logs.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock();self.requests=0;self.errors=0;self.predictions=0;self.seconds=0.;self.by_label={k:0 for k in ['positive','negative','neutral']}
    def record(self,status,elapsed,outputs):
        event={'time':datetime.now(timezone.utc).isoformat(),'request_id':uuid.uuid4().hex,'status':status,'seconds':elapsed,'model_version':self.bundle['run_id'],'predictions':[{'sentiment':r['sentiment'],'confidence':r['confidence'],'word_count':r['word_count']} for r in outputs]}
        with self.lock:
            self.requests+=1;self.errors+=int(status>=400);self.seconds+=elapsed;self.predictions+=len(outputs)
            for r in outputs:self.by_label[r['sentiment']]+=1
            with (self.logs/'requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
    def metrics(self):
        with self.lock:
            return {'requests':self.requests,'errors':self.errors,'predictions':self.predictions,'latency_seconds_sum':self.seconds,'by_label':dict(self.by_label),'model_version':self.bundle['run_id'],'scope':'Current process; JSONL log persists across restarts'}

def make_server(host='127.0.0.1',port=8000,artifacts='artifacts',logs='logs'):
    state=State(artifacts,logs)
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(15)
        def log_message(self,*args):pass
        def send(self,status,payload,kind='application/json'):
            data=json.dumps(payload).encode() if kind=='application/json' else payload.encode()
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(data)))
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            routes={'/report/metrics':'metrics.json','/report/quality':'data_quality.json','/report/drift':'drift.json','/report/drift-simulation':'drift_simulation.json','/report/responsible-ai':'responsible_ai.json','/report/manifest':'manifest.json'}
            if self.path=='/':return self.send(200,Path(__file__).with_name('dashboard.html').read_text(),'text/html')
            if self.path=='/health':return self.send(200,{'status':'ready','model_version':state.bundle['run_id']})
            if self.path=='/monitoring':return self.send(200,state.metrics())
            if self.path=='/metrics':
                m=state.metrics();lines=['# TYPE news_requests_total counter',f'news_requests_total {m["requests"]}',f'news_errors_total {m["errors"]}',f'news_predictions_total {m["predictions"]}',f'news_request_duration_seconds_sum {m["latency_seconds_sum"]}',f'news_request_duration_seconds_count {m["requests"]}']
                lines += [f'news_predictions_by_label_total{{label="{k}"}} {v}' for k,v in m['by_label'].items()]
                return self.send(200,'\n'.join(lines)+'\n','text/plain')
            if self.path in routes:return self.send(200,json.loads((state.run/routes[self.path]).read_text()))
            return self.send(404,{'error':'Route not found'})
        def do_POST(self):
            start=time.perf_counter();status=200;outputs=[]
            try:
                if self.path not in ['/predict','/batch']:
                    status=404;return self.send(status,{'error':'Route not found'})
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ValueError('Invalid Content-Length')
                if not 0<length<=MAX_BODY:
                    status=413;return self.send(status,{'error':'Body must be between 1 byte and 2 MB'})
                body=self.rfile.read(length)
                if self.path=='/predict':
                    if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('Use application/json')
                    payload=json.loads(body)
                    if not isinstance(payload,dict):raise ValueError('JSON must be an object')
                    outputs=predict(state.bundle,[payload],explain=True)
                    self.send(200,outputs[0])
                else:
                    if not self.headers.get('Content-Type','').startswith('text/csv'):raise ValueError('Use text/csv')
                    reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
                    if not reader.fieldnames or 'title' not in reader.fieldnames:raise ValueError('CSV requires title column')
                    rows=[]
                    for row in reader:
                        rows.append({'title':row.get('title'),'description':row.get('description') or ''})
                        if len(rows)>500:raise ValueError('HTTP batch limit is 500 rows; use CLI for larger files')
                    outputs=predict(state.bundle,rows);self.send(200,{'count':len(outputs),'predictions':outputs})
            except (ValueError,UnicodeDecodeError,TypeError,csv.Error) as exc:
                status=400;self.send(status,{'error':str(exc)})
            except Exception:
                status=500;self.send(status,{'error':'Internal inference error'})
            finally:state.record(status,time.perf_counter()-start,outputs)
    server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True
    return server

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8000);p.add_argument('--artifacts',default=os.environ.get('ARTIFACTS_DIR','artifacts'));p.add_argument('--logs',default=os.environ.get('LOG_DIR','logs'));a=p.parse_args()
    server=make_server(a.host,a.port,a.artifacts,a.logs);print(f'News dashboard and API at http://{a.host}:{a.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

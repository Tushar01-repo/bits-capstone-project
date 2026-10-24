"""Verify a running Grafana add-on without saving credentials."""
import argparse
import base64
from datetime import datetime, timezone
from getpass import getpass
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--grafana',default='http://127.0.0.1:3000')
    parser.add_argument('--prometheus',default='http://127.0.0.1:9090')
    parser.add_argument('--output',default='grafana-verification.json')
    args=parser.parse_args()
    username=input('Grafana username [admin]: ').strip() or 'admin'
    password=getpass('Grafana password (not saved): ')
    header='Basic '+base64.b64encode((username+':'+password).encode()).decode()
    def read(base,path,auth=False):
        request=Request(base.rstrip('/')+path,headers={'Authorization':header} if auth else {})
        with urlopen(request,timeout=20) as response:return json.load(response)
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'checks':{},'status':'failed'}
    try:
        health=read(args.grafana,'/api/health');result['checks']['grafana_database']=health.get('database')=='ok'
        datasource=read(args.grafana,'/api/datasources/uid/news-prometheus/health',True)
        result['checks']['prometheus_datasource']=datasource.get('status')=='OK'
        dashboard=read(args.grafana,'/api/dashboards/uid/news-sentiment-ops',True)['dashboard']
        result['checks']['dashboard_loaded']=len(dashboard.get('panels',[]))==12
        query=read(args.prometheus,'/api/v1/query?query=up%7Bjob%3D%22news-sentiment%22%7D')
        series=query.get('data',{}).get('result',[])
        result['checks']['app_scrape_up']=bool(series) and all(float(x['value'][1])==1 for x in series)
        result['grafana_version']=health.get('version');result['dashboard_title']=dashboard.get('title')
        result['status']='passed' if all(result['checks'].values()) else 'failed'
    except (HTTPError,URLError,KeyError,ValueError) as exc:
        result['error']=('HTTP '+str(exc.code)) if isinstance(exc,HTTPError) else str(exc)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    print('Credentials were not written to the report.')
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())

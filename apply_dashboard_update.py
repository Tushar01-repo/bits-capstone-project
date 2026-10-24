"""Apply only dashboard/API update files, with verified payload and backups."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import uuid


def apply(project):
    project=Path(project).resolve()
    if not (project/'newsml'/'core.py').is_file():
        raise SystemExit('Run from your news-sentiment-mlops folder, or pass --project PATH.')
    payload=Path(__file__).resolve().parent/'dashboard_update_payload'
    manifest=json.loads((payload/'manifest.json').read_text(encoding='utf-8'))
    # Validate all payload files before making any changes.
    for name,expected in manifest.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Invalid update path')
        source=payload/rel
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise SystemExit('Update checksum mismatch: '+name)
        if source.suffix=='.py':compile(source.read_text(encoding='utf-8'),name,'exec')
    backup=project.parent/'news-dashboard-update-backups'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    prior={};applied=[]
    for name in manifest:
        target=project/name;prior[name]=target.exists()
        if target.exists():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
    try:
        for name in manifest:
            target=project/name;target.parent.mkdir(parents=True,exist_ok=True);applied.append(name);shutil.copy2(payload/name,target)
    except Exception:
        for name in reversed(applied):
            if prior[name]:shutil.copy2(backup/name,project/name)
            else:(project/name).unlink(missing_ok=True)
        raise
    print('Updated '+str(len(manifest))+' dashboard/API/sample/test/documentation files.')
    print('Backups: '+str(backup))
    print('Your models, raw data, requirements.txt and compose.yaml were not changed.')
    print('Docker: docker compose up -d --build --wait app')
    print('Then open http://127.0.0.1:8002 and press Ctrl+F5.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',default='.');args=parser.parse_args();apply(args.project)

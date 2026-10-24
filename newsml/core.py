"""Shared text validation, inference and faithful linear-model explanations."""
import hashlib
import json
import re
from pathlib import Path
import joblib
import numpy as np

LABELS = ['negative', 'neutral', 'positive']
LEAKAGE_COLUMNS = ['compound', 'pos', 'neg', 'neu', 'sentiment_cat', 'source_weight']

def normalize(text):
    return re.sub(r'\W+', ' ', str(text).casefold()).strip()

def text_input(title, description=''):
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title must be a nonempty string')
    if not isinstance(description, str):
        raise ValueError('description must be a string')
    if len(title) > 2000 or len(description) > 20000:
        raise ValueError('title limit is 2000 characters; description limit is 20000')
    return title.strip() + ' ' + description.strip()

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')

def load_bundle(root='artifacts'):
    root = Path(root)
    current = json.loads((root / 'current.json').read_text())
    run = root / current['run_id']
    # Load only locally trained/trusted joblib files; pickle is executable.
    if sha256(run / 'model.joblib') != current['model_sha256']:
        raise ValueError('Model checksum mismatch')
    return joblib.load(run / 'model.joblib'), run

def predict(bundle, records, explain=False):
    if not isinstance(records, list) or not 1 <= len(records) <= 500:
        raise ValueError('records must contain 1 to 500 objects')
    if any(not isinstance(r, dict) for r in records):
        raise ValueError('each record must be an object')
    texts = [text_input(r.get('title'), r.get('description', '')) for r in records]
    model = bundle['pipeline']
    probabilities = model.predict_proba(texts)
    out = []
    vec = model.named_steps['tfidf']
    features = vec.get_feature_names_out()
    matrix = vec.transform(texts)
    for i, p in enumerate(probabilities):
        k = int(np.argmax(p)); label = str(model.classes_[k])
        item = {'sentiment': label, 'probabilities': {str(c): float(v) for c,v in zip(model.classes_,p)},
                'confidence': float(p[k]), 'needs_review': bool(p[k] < bundle['review_threshold']),
                'model_version': bundle['run_id'], 'word_count': len(texts[i].split())}
        if explain:
            row = matrix.getrow(i)
            contributions = row.data * model.named_steps['classifier'].coef_[k, row.indices]
            ix = np.argsort(np.abs(contributions))[::-1][:10]
            item['explanation'] = {'class':label, 'intercept':float(model.named_steps['classifier'].intercept_[k]),
                'terms':[{'term':str(features[row.indices[j]]),'contribution':float(contributions[j])} for j in ix],
                'meaning':'Contributions to the predicted class logit; not causal evidence or a financial rationale.'}
        out.append(item)
    return out

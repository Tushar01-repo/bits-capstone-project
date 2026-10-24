"""On-demand CSV evaluation and drift checks for the loaded model."""
import csv
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from .core import LABELS, normalize, predict, text_input
from .monitor import drift_report

MAX_ROWS = 500
LABEL_COLUMNS = ('sentiment', 'sentiment_cat', 'human_label', 'label')

def read_upload(body, labeled=False):
    reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')), strict=True)
    fields = reader.fieldnames or []
    if len(set(fields)) != len(fields):
        raise ValueError('CSV has duplicate column names')
    if 'title' not in fields:
        raise ValueError('CSV requires a title column; description is optional')
    candidates = [c for c in LABEL_COLUMNS if c in fields]
    if labeled and len(candidates) != 1:
        raise ValueError('Evaluation needs exactly one label column: sentiment, sentiment_cat, human_label or label')
    label_column = candidates[0] if labeled else None
    rows = []
    for number, row in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            raise ValueError('Upload limit is 500 rows')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'CSV row {number} has the wrong number of fields')
        item = {'title':row['title'], 'description':row.get('description', '')}
        try:
            text_input(item['title'], item['description'])
        except ValueError as exc:
            raise ValueError(f'CSV row {number}: {exc}') from exc
        if labeled:
            label = row[label_column].strip().lower()
            if label not in LABELS:
                raise ValueError(f'CSV row {number}: label must be negative, neutral or positive')
            item['expected_sentiment'] = label
        rows.append(item)
    if not rows:
        raise ValueError('CSV contains no data rows')
    return rows, label_column

def metadata(bundle, body, rows):
    return {'model_version':bundle['run_id'], 'created_at':datetime.now(timezone.utc).isoformat(),
            'input_sha256':hashlib.sha256(body).hexdigest(), 'rows':len(rows)}

def evaluate_upload(bundle, run, body):
    rows, label_column = read_upload(body, labeled=True)
    predictions = predict(bundle, rows)
    truth = [r['expected_sentiment'] for r in rows]
    predicted = [p['sentiment'] for p in predictions]
    counts = {label:truth.count(label) for label in LABELS}
    warnings = ['Scores measure agreement with uploaded labels. Their correctness and independence are not verified.']
    if len(rows) < 100:
        warnings.append('Small evaluation set: results may be unstable; this is not a robust accuracy benchmark.')
    missing = [label for label,count in counts.items() if not count]
    if missing:
        warnings.append('No reference examples for: '+', '.join(missing)+'. Macro-F1 still averages all three classes, assigning zero where undefined.')
    normalized = [normalize(r['title']) for r in rows]
    duplicates = len(normalized) - len(set(normalized))
    if duplicates:
        warnings.append(f'{duplicates} repeated normalized titles; duplicates can distort metrics.')
    train_path = Path(run)/'train.csv'
    overlap = None
    if train_path.exists():
        known = set(pd.read_csv(train_path, usecols=['title']).title.fillna('').map(normalize))
        overlap = sum(t in known for t in normalized)
        if overlap:
            warnings.append(f'{overlap} rows match training titles. This upload is not an independent held-out evaluation.')
    else:
        warnings.append('Training title file unavailable; training overlap was not checked.')
    details = [{'row':i+1, **r, 'predicted_sentiment':p['sentiment'], 'correct':r['expected_sentiment']==p['sentiment'],
                'confidence':p['confidence'], 'probabilities':p['probabilities']} for i,(r,p) in enumerate(zip(rows,predictions))]
    return {**metadata(bundle,body,rows), 'operation':'evaluation','label_column':label_column,
            'accuracy':float(accuracy_score(truth,predicted)),
            'macro_f1':float(f1_score(truth,predicted,labels=LABELS,average='macro',zero_division=0)),
            'classification_report':classification_report(truth,predicted,labels=LABELS,output_dict=True,zero_division=0),
            'confusion_matrix':confusion_matrix(truth,predicted,labels=LABELS).tolist(), 'label_order':LABELS,
            'label_counts':counts,'duplicate_title_rows':duplicates,'training_title_overlap_rows':overlap,
            'incorrect_rows':sum(not r['correct'] for r in details),'warnings':warnings,'predictions':details}

def drift_upload(bundle, run, body):
    rows,_ = read_upload(body)
    if len(rows)<20:
        raise ValueError('Drift checking requires at least 20 news rows. Your upload has '+str(len(rows))+'.')
    reference_path = Path(run)/'reference.csv'
    if not reference_path.exists():
        raise ValueError('The loaded model has no reference.csv. Generate reference data with the training pipeline first.')
    result = drift_report(bundle, pd.read_csv(reference_path), pd.DataFrame(rows))
    result.update(metadata(bundle,body,rows))
    result['operation'] = 'drift'
    result['reference'] = 'Saved training reference for the loaded model'
    result['warnings'] = ['Drift alerts are heuristic signals for investigation, not proof of lower accuracy.']
    if len(rows)<100:
        result['warnings'].append('Small drift window; use a larger representative sample for reliable monitoring.')
    normalized = [normalize(r['title']) for r in rows]
    result['duplicate_title_rows'] = len(normalized)-len(set(normalized))
    if result['duplicate_title_rows']:
        result['warnings'].append('Repeated titles can distort drift statistics.')
    return result

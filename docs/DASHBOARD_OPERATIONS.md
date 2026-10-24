# Interactive evaluation and drift update

## New dashboard actions

- **Evaluate a labeled CSV:** upload 1–500 rows containing `title`, optional `description`, and exactly one of `sentiment`, `sentiment_cat`, `human_label`, `label`. Labels are case-insensitive positive/neutral/negative. Shows accuracy, macro-F1, per-class precision/recall, confusion matrix and incorrect predictions. Download the full JSON or per-row CSV.
- **Check drift:** upload 20–500 news rows without requiring labels. Compares with `reference.csv` belonging to the server's loaded model. Displays text-length, vocabulary and prediction-distribution changes with actual thresholds. Download JSON.
- **Live operations:** refreshes every five seconds while the page is visible. Shows POST requests, failures, prediction-row counts, mean latency and counts per endpoint. Counters reset at server restart. Prediction-row totals exclude evaluation/drift diagnostic work.
- **Saved training reports:** remain immutable historical reports. Refresh does not retrain or rerun analysis.

Both uploads have a 2 MB limit. Empty/invalid labels, malformed CSV, duplicate headers and too few drift rows return an actionable error. Inputs are not saved to the server. Results remain in the page until reload; use download to retain them. No model retraining or promotion occurs. Existing reference and model artifacts stay read-only.

## Label and drift interpretation

Uploaded labels are user-supplied, not automatically human-verified. Use an independently labeled unseen dataset for a defensible quality claim. The UI warns about small evaluation samples, missing classes, duplicate titles and matching training titles (when train.csv exists). Title overlap detection does not detect paraphrases or prove independence. Macro-F1 averages the fixed three classes even when a class has no support; undefined metrics are zero and a warning is shown.

A 12-row fictional evaluation sample with AI-authored illustrative labels can be downloaded from the panel. It is only a functionality demo. A separate 30-row fictional sports sample deliberately demonstrates a shift from financial news. Neither is a real-world benchmark. Drift flags are heuristic and do not prove accuracy loss.

The existing reserved-human-review CLI is unchanged. Upload evaluation is exploratory and does not replace the reserved test-set protocol or overwrite metrics.json.

## New API endpoints

POST `/evaluate` with `Content-Type: text/csv` returns metrics, row results, warnings, model version, timestamp and input hash.
POST `/drift` with `Content-Type: text/csv` returns drift statistics, thresholds, warnings and provenance.
GET `/examples/evaluation.csv` and `/examples/drift.csv` supply the explicitly synthetic samples.

## Checks performed

16 local unit/integration checks pass, including known-score evaluation, confusion counts, invalid uploads, label aliases, training overlap warnings, drift identity/shift, read-only model pointer and live operation counters. Both upload endpoints were also exercised with the bundled trained model and served sample files. Dashboard JavaScript syntax was checked. Browser interaction tests were extended, but could not execute here because Chromium is unavailable. Docker needs to be rebuilt on your machine to serve this update.

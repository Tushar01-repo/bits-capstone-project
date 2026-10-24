# Model card

## Intended use
Educational financial-news snippet sentiment classification. Input: headline plus optional description. Output: negative, neutral, positive, uncalibrated probabilities, review flag and linear-model contributions. English text is intended; automatic language filtering is not implemented. No company-specific event detection or stock-return prediction.

## Dataset and labels
User-supplied news_sentiment_raw.csv. Original file: 12,051 rows. All original labels agree with compound-score thresholds at +/-0.05. This suggests weak/automated supervision, not verified human ground truth. Exact upstream annotation tool, collection method, publisher authenticity and license are unknown. No external URLs were crawled or verified. Keep raw text private until redistribution permission is confirmed.

## Cleaning
Drop seed-corpus.local entries, removed/empty titles, invalid dates/labels. Fill absent descriptions with empty strings. Keep earliest instance per case/punctuation-normalized headline. This conservative rule can remove genuinely different daily stories with the same headline; quarantined duplicate rows are retained for inspection. Near-duplicates with different headlines may remain. Do not call the data fully deduplicated or language-validated.

## Evaluation
Reserve up to 300 records before training for future human review. Remaining unique-title groups are sorted chronologically and split approximately 70/15/15 at whole-day boundaries. Fit TF-IDF on training text only. Select C from 0.5 and 2.0 on validation macro-F1. Freeze that train-only model and evaluate on test. Report majority baseline, accuracy, macro-F1, per-class metrics, log loss and confusion matrix. Metrics measure agreement with weak labels. Do not use test for retuning.

## Explainability and reliability
Predicted-class TF-IDF × coefficient contributions explain the model's logit, not causality or an expert financial interpretation. Topic/source slices with >=30 test items are descriptive error analysis; they do not prove fairness. Probabilities are not calibrated. Review cutoff 0.60 is a transparent heuristic, not a confidence guarantee. Neutral has fewer examples; class weighting is applied. Multiple-company perspectives, mixed news, sarcasm, truncation, negation and non-English text are failure risks.

## Monitoring
KS text-length effect size + p-value, n-gram OOV difference, Jensen-Shannon distance of predicted labels. Thresholds are initial heuristics. Synthetic sports/length-shift report demonstrates the mechanism only. Real accuracy degradation requires newly labeled data. No automatic promotion/retraining from a drift alert.

## Human review
Use human_review_template.csv; populate human_label, reviewer, rationale. Original weak labels are hidden in the template. Review only available headline/snippet; do not infer absent facts. Decide sentiment of the overall supplied text consistently. Use rationale to flag ambiguous cases for adjudication before final labeling. At least two reviewers on a subset is advisable. The evaluator rejects unreviewed rows and non-reserved IDs, and reads original reserved text to prevent accidental input edits. Repeated use of this set for tuning would invalidate its holdout role.

## Operational limits
The bounded standard-library HTTP service is a local capstone demonstration, not an internet-hardened production gateway. Bind to localhost; hosted use needs a private network or authenticated TLS reverse proxy, rate limiting and load testing. Body and batch limits are enforced. No raw news text is written to request telemetry. Metrics are process-local; JSONL is persistent. Do not load untrusted joblib/pickle artifacts. Model checksum detects accidental alteration, not malicious replacement of both artifact and manifest.

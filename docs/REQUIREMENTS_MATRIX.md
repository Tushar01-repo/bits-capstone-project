# Assignment requirements and evidence

Source: supplied AI Engineering & MLOps video submission guidelines. This maps to that document only; any separate course specification still applies.

| Phase | Implementation | Evidence | Remaining external action |
|---|---|---|---|
| 1 Data pipeline | newsml/pipeline.py: validation, quarantine, duplicate handling, day-boundary chronological splits | data_quality.json; rejected.csv; duplicates.csv; split CSVs; execution.jsonl | Demonstrate live command |
| 2 Model training | Train-only TF-IDF and balanced logistic regression; validation selects C; test stays untouched | metrics.json; model.joblib; manifest.json; execution.jsonl | Explain automated-label limitations |
| 3 Serving | HTTP /predict, /batch; CSV batch CLI | golden_path.json; batch_predictions.csv; API responses | Demonstrate both inference modes |
| 4 CI/CD and infrastructure | CI tests/build/container test; manually dispatched private-host deployment; Dockerfile/Compose | Local tests are included; GitHub logs and Docker status must come from actual execution | Push repo; execute CI; provision runner/Docker host; run deployment |
| 5 Monitoring and drift | JSONL request telemetry, Prometheus endpoint/config/alerts, offline drift CLI | requests.jsonl; /monitoring; /metrics; drift.json; drift_simulation.json | Run hosted monitoring if using Compose; simulation must be identified |
| 6 Responsible AI | Exact linear term contributions, source/topic error slices, labeling limitations, reserved annotation set | responsible_ai.json; model card; human-review template | Human review remains pending; explanation/error analysis already implemented |
| 7 Dashboard | Same-origin browser UI for single/batch predictions and report browsing | Open localhost:8000; submit news; download batch output | Record actual interaction |
| 8 Golden path | golden_path.py rebuilds and runs tests, trains, evaluates, batch predicts, and checks HTTP endpoints | golden_path.json; manifest/input/model hashes; README | Re-run from fresh environment and show command/logs |

Human review is a quality enhancement, not a claim that the PDF mandates a specific annotation exercise. Do not describe source/topic error slices as demographic fairness validation. This project does not train company-event detection because the provided dataset has no such labels.

Configuration files are not proof of deployment. Never claim GitHub Actions, Docker, hosted infrastructure, or human evaluation passed until they actually have.

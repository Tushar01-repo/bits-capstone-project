# Grafana dashboard for News Signal

This add-on attaches Grafana to your existing Docker Compose project and Prometheus. It does not replace compose.yaml, change port 8002, touch the model or retrain. It works with either the original app or the interactive evaluation/drift update.

## Install

Extract the contents into your existing `C:\Users\paltu\news-sentiment-mlops` folder. The new `compose.grafana.yaml` must sit beside your existing `compose.yaml`; the new configuration lives under `infra/grafana/`.

Run from that project folder:

```powershell
docker compose -f compose.yaml -f compose.grafana.yaml --profile monitoring up -d --wait prometheus grafana
```

Open **http://127.0.0.1:3000**. On a fresh Grafana volume the login is **admin / admin**; choose a new password when prompted. If you already initialized this Grafana volume, use its existing password.

The dashboard and Prometheus data source are provisioned automatically. The home dashboard should be **News Signal · Service Operations**. Otherwise open Dashboards → News Signal → News Signal · Service Operations, or use:

http://127.0.0.1:3000/d/news-sentiment-ops

No Grafana Cloud account or external plugin is required. Grafana is bound only to localhost. The add-on pins the official grafana/grafana:13.2.4 image.

## Dashboard panels

| Panel | Interpretation |
|---|---|
| Application scrape status | UP means Prometheus can scrape the app; not a prediction-quality check |
| POST requests since restart | Calls to single/batch prediction and, when installed, evaluation/drift |
| Prediction rows since restart | News items predicted through /predict and /batch |
| Failed requests since restart | 4xx validation errors plus 5xx server failures |
| Requests/minute | Five-minute smoothed POST rate |
| Failures/minute | Five-minute smoothed unsuccessful POST rate |
| Mean latency | Mean POST duration over five minutes; includes evaluation/drift |
| Failed POST percentage | Errors / requests over five minutes |
| Sentiment totals | Positive/neutral/negative prediction counters |
| Sentiment prediction rate | Predicted news items/minute by label |
| Availability history | Successful (1) versus failed (0) scrapes |
| Interpretation notes | Counter, rate, retention and model-quality limitations |

Refresh is every 15 seconds. Default time range is the last 30 minutes. Rate panels require at least two scrapes; give a new instance 30–60 seconds and generate requests. Idle latency/error-percentage windows can show no value because there are no requests to average. That is not proof of an error. Process counters reset when the app restarts; Prometheus rate handles resets.

The dashboard does not invent p95/p99, accuracy, per-endpoint latency, or data-drift metrics. The app currently does not export those. Use the app dashboard for evaluation and drift. Grafana uses `http://prometheus:9090` internally; Prometheus continues scraping `app:8000`, regardless of your browser's host port 8002.

## Generate traffic

```powershell
$body = @{ title = 'Company reports higher profits'; description = 'Revenue increased.' } | ConvertTo-Json
1..3 | ForEach-Object {
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/predict -ContentType 'application/json' -Body $body
}
```

Wait 15–30 seconds and inspect the counters. With no other traffic they rise by three. A successful batch of ten rows adds one request and ten predictions.

## Verify and collect evidence

```powershell
docker compose -f compose.yaml -f compose.grafana.yaml --profile monitoring ps
python .\scripts\verify_grafana.py
```

The optional verifier prompts for your Grafana credentials (never saves them), checks Grafana database health, provisioned data source connectivity, dashboard loading and the app's Prometheus target. It writes `grafana-verification.json`. Save that result and capture the dashboard showing real traffic for your capstone monitoring phase. This report is created only when YOU execute the verifier; no successful deployment is preclaimed.

## Troubleshooting

Connection refused:

```powershell
docker compose -f compose.yaml -f compose.grafana.yaml --profile monitoring logs --tail 80 grafana
```

Port 3000 occupied: choose a free host port without killing processes:

```powershell
$env:GRAFANA_PORT = '3001'
docker compose -f compose.yaml -f compose.grafana.yaml --profile monitoring up -d --wait grafana
```

Then use http://127.0.0.1:3001 and run the verifier with `--grafana http://127.0.0.1:3001`. Set the same environment variable in future terminals when using that port.

No data: confirm the Prometheus target is UP and named `news-sentiment`; confirm the Grafana data source URL is `http://prometheus:9090`; generate traffic and refresh. Query `news_requests_total` in Prometheus to distinguish collection issues from display issues.

Grafana saves login/settings in the new named `grafana-data` volume. Do not use `down -v`: that can delete this project's model and monitoring volumes. Use both `-f` arguments for future Grafana operations. Your existing base Compose commands still manage app/Prometheus; they may report Grafana as an orphan because its definition is in the add-on file. Do not use `--remove-orphans` with only the base file if you want to retain Grafana.

The add-on does not change your Prometheus storage. If your original Prometheus service has no persistent volume, recreating it can lose historical samples. Grafana's volume stores dashboards/settings, not Prometheus history.

## Editing

The provisioned dashboard is read-only in the UI. To customize, use Save as copy in Grafana or edit `infra/grafana/dashboards/news-sentiment.json`; provisioning polls every 30 seconds. Changes to provisioning/data-source configuration may require restarting Grafana.

## Validation performed before delivery

JSON/YAML parsing, panel layout/IDs, datasource UID consistency, metric-name matching against the app and Compose add-on boundaries were checked. The verifier was exercised against mocked HTTP success/failure responses. Docker/Grafana runtime and rendered dashboard appearance were not verified in the assistant environment because Docker is unavailable. Use the commands above to complete that validation on your machine.

Official references:
- https://grafana.com/docs/grafana/latest/administration/provisioning/
- https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/
- https://grafana.com/grafana/download/13.2.4?edition=oss&platform=docker

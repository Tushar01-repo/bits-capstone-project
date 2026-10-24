# Verification and completion status

## Actual dataset run

Run ID: 20261022T183835Z-16e7f0. These numbers come from the supplied dataset and saved run artifacts, not synthetic test fixtures.

| Measure | Result |
|---|---:|
| Raw rows | 12,051 |
| Quarantined seed records | 15 |
| Removed repeated normalized-title rows | 574 |
| Clean rows | 11,462 |
| Training rows | 7,834 |
| Validation rows | 1,693 |
| Chronological test rows | 1,635 |
| Reserved future human-review rows | 300 |
| Selected logistic-regression C | 2.0 |
| Test accuracy | 0.713761 |
| Test macro-F1 | 0.609561 |
| Majority-class test accuracy | 0.521713 |
| Negative F1 | 0.725041 |
| Neutral F1 | 0.320475 |
| Positive F1 | 0.783168 |

The baseline improves on majority accuracy, but neutral sentiment remains weak. All metrics above are against automated labels. Independent human-reviewed quality is unknown. Do not describe this as a production-ready financial signal engine.

## Completed locally

- Trained and selected two candidate CPU models on the real input.
- Generated data-quality, evaluation, explanation, error-slice and drift artifacts.
- Executed the complete golden path successfully, including 1,635 batch predictions and live HTTP requests.
- Passed 12 unittest integration/behavior checks: day-boundary chronology, group disjointness, duplicate filtering, schema rejection, score-field exclusion, probability outputs, explanation fidelity, batch consistency, drift identity/shift, HTTP endpoints, malformed/oversize request rejection, unreviewed annotation rejection and manifest integrity (some are combined in one test).
- Dashboard HTTP delivery verified; embedded JavaScript passes Node syntax checking.
- Retained actual execution logs and artifact hashes.

## Not executed or not completed

- Browser-rendered visual/interaction verification: Playwright was installed but the Chromium binary was absent; its download failed. No browser screenshot or visual QA is claimed.
- Docker build/Compose and Prometheus runtime: Docker is not installed in this environment.
- GitHub CI/CD: workflow files supplied but no run in the user's GitHub account.
- Remote hosting/public repository: not created. Private-host deployment workflow and instructions supplied.
- Fresh OS/venv dependency installation: not executed; code ran against the matching preinstalled pinned packages.
- Human labeling: 300-row blind template supplied, no human verification fabricated.
- Dataset origin/license: upstream URL was not supplied and rights remain unverified.
- Submission recording: requires learner voice, webcam/BITS ID and actual desktop evidence.

## Packaging

The private ZIP includes source, docs, requirements, tests, CI/CD and Docker configuration, original user input, the latest successful trained run, and execution logs. Older intermediate runs, caches and runtime telemetry outside the successful run are omitted. No git repository or public URL is claimed. The source snapshot SHA-256 inventory is provided in SOURCE_SHA256.json for traceability until you initialize/commit to your repository.

## Follow-up automation

Added scripts/run_all.ps1 for pipeline, browser checks, Docker and monitoring, plus tests/browser.cjs and a browser test stage in CI. Browser tests cover prediction, CSV upload/download, report switching, invalid input and mobile overflow. Their JavaScript syntax and fixture-server startup were checked locally; browser execution remains blocked by missing Chromium. Docker and GitHub connection checks confirmed no Docker runtime and no connected GitHub account. Package-manager installation failed due to environment permission restrictions. These are not successful deployment results.

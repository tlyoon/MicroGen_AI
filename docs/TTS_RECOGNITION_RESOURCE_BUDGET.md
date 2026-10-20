# PR #49 — bounded recognition workload

The unattended QA pipeline estimates total requested audio seconds and audio-model request count from the actual WAV frame headers **before** any paid API call. Defaults cap total input duration at 1,200 seconds across two independent passes, cap at 120 model requests and 18 MB per WAV. Every threshold is configurable; exceeding a cap fails before recognition, without silently skipping slides or claiming QA. This is a conservative **resource budget**, NOT a currency cost estimate, actual billing estimate or API quota guarantee. Only complete, two-pass checks may pass the release gate.

CLI `--max-input-audio-seconds`, `--max-recognition-requests` adjust conservative caps. Original teaching assets stay unchanged.

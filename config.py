"""Channel roster and lookback window for the alert dashboard."""

import os

# Defaults to 1 (today's alerts only) so a run stays fast. Set
# ALERT_LOOKBACK_DAYS to a larger number for more history, or to 0 for each
# channel's full history — the timeframe picker in the dashboard itself can
# then filter that wider pull down to whatever range is actually wanted.
_lookback_env = os.environ.get("ALERT_LOOKBACK_DAYS")
LOOKBACK_DAYS = int(_lookback_env) if _lookback_env else 1

# channel_name -> (environment, default_category)
# category is a fallback; the analyzer re-classifies per-message from content.
CHANNELS = {
    "devops-gnoc-alerts":          ("shared",  "infra"),
    "prod-critical-alert":         ("prod",    "infra"),
    "devops-prod-sql-alerts":      ("prod",    "infra"),
    "v2-prod-sql-alarm":           ("prod",    "infra"),
    "prod-debezium-alerts":        ("prod",    "process"),
    "dart-etl-airflow-prod-alert": ("prod",    "process"),
    "signoz-prd-alerts":           ("prod",    "infra"),
    "devops-kubernetes-alerts":    ("shared",  "pod"),
    "snow-flake-alerts":           ("shared",  "infra"),
    "spot-node-eviction":          ("shared",  "infra"),
    "prod-etl-job-alert":          ("prod",    "process"),
    "prod-backup-alert":           ("prod",    "infra"),
    "v1-alarms":                   ("shared",  "infra"),
    "v2-prod-alarms":              ("prod",    "infra"),
}

CATEGORIES = ("infra", "pod", "process")
ENVIRONMENTS = ("prod", "uat", "qa", "shared")

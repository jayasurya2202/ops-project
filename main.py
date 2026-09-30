"""Entry point: pull today's alerts from the configured Slack channels by
default, analyze each with Claude, and write a self-contained HTML
dashboard to src/output/dashboard.html.

Required env vars:
  SLACK_BOT_TOKEN      xoxb-... token, invited into every channel in config.py
  ANTHROPIC_API_KEY    Claude API key

Optional env vars:
  ALERT_LOOKBACK_DAYS       default 1 (today); set N for the last N days, or 0 for full history
  MAX_ALERTS_PER_CHANNEL    default 200 (safety cap on Claude calls)
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from config import CHANNELS, LOOKBACK_DAYS
from slack_client import SlackClient, SlackError
from analyzer import Analyzer
from aggregator import summarize
from dashboard import generate_html

MAX_ALERTS_PER_CHANNEL = int(os.environ.get("MAX_ALERTS_PER_CHANNEL", "200"))
ANALYSIS_CONCURRENCY = int(os.environ.get("ANALYSIS_CONCURRENCY", "6"))
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "dashboard.html")
# Caches channel_name -> channel_id so conversations.list (slow/rate-limited)
# only runs for channels not already resolved. Delete this file to force a
# full re-resolution, e.g. after a channel is renamed in Slack.
CACHE_PATH = os.path.join(os.path.dirname(__file__), ".channel_id_cache.json")

# Slack message subtypes that are never real alerts.
SKIP_SUBTYPES = {"channel_join", "channel_leave", "channel_topic", "channel_purpose"}


def message_text(msg):
    """Alerts often arrive as bot messages with the real content in
    attachments/blocks rather than top-level 'text'. Pull whatever is there."""
    parts = [msg.get("text", "")]
    for att in msg.get("attachments", []):
        for key in ("title", "text", "fallback"):
            if att.get(key):
                parts.append(att[key])
    return "\n".join(p for p in parts if p).strip()


def load_channel_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_channel_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)


def main():
    sys.stdout.reconfigure(line_buffering=True)

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not slack_token or not anthropic_key:
        print("Set SLACK_BOT_TOKEN and ANTHROPIC_API_KEY before running.", file=sys.stderr)
        sys.exit(1)

    slack = SlackClient(slack_token)
    analyzer = Analyzer(anthropic_key)

    if LOOKBACK_DAYS:
        oldest_ts = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp()
    else:
        oldest_ts = 0  # full channel history

    cache = load_channel_cache()
    missing = [name for name in CHANNELS if name not in cache]
    if missing:
        print(f"Resolving {len(missing)} channel name(s) to IDs (not cached yet)...")
        cache.update(slack.resolve_channel_ids(missing))
        save_channel_cache(cache)
    else:
        print(f"Using cached channel IDs for all {len(CHANNELS)} channels.")
    ids = {name: cache[name] for name in CHANNELS if name in cache}

    analyzed = []
    for channel_name, (env, default_category) in CHANNELS.items():
        channel_id = ids.get(channel_name)
        if not channel_id:
            continue
        print(f"Fetching #{channel_name} ({env})...")
        try:
            messages = slack.fetch_history(channel_id, oldest_ts)
        except SlackError as e:
            print(f"  [warn] {e}")
            continue

        real_alerts = [
            m for m in messages
            if m.get("subtype") not in SKIP_SUBTYPES and message_text(m)
        ][:MAX_ALERTS_PER_CHANNEL]
        window_desc = f"in the last {LOOKBACK_DAYS}d" if LOOKBACK_DAYS else "(full channel history)"
        print(f"  {len(real_alerts)} alert messages {window_desc}")

        def analyze_one(msg):
            text = message_text(msg)
            analysis = analyzer.analyze(text, channel_name, env, default_category)
            ts = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).isoformat()
            return {
                "channel": channel_name,
                "env": analysis["env"],  # parsed from the alert content, not just the channel
                "timestamp": ts,
                "raw_excerpt": text[:2000],
                "analysis": analysis,
            }

        with ThreadPoolExecutor(max_workers=ANALYSIS_CONCURRENCY) as pool:
            futures = [pool.submit(analyze_one, msg) for msg in real_alerts]
            for future in as_completed(futures):
                try:
                    analyzed.append(future.result())
                except Exception as e:
                    print(f"  [warn] analysis failed for one message: {e}")

    if not analyzed:
        print("No alerts found (check bot channel invites / token scopes).")

    summary = summarize(analyzed)
    html = generate_html(
        analyzed, summary, LOOKBACK_DAYS,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)

    print(f"\nDashboard written to {OUTPUT_PATH}")
    print(f"Total alerts analyzed: {summary['total']}")


if __name__ == "__main__":
    main()

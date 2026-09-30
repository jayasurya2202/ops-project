"""Thin wrapper over the Slack Web API: resolve channel names to IDs and page
through conversations.history for a lookback window."""

import time
import requests

SLACK_API = "https://slack.com/api"


class SlackError(RuntimeError):
    pass


class SlackClient:
    def __init__(self, bot_token):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bot_token}"})

    def _get(self, method, params, max_retries=5):
        for attempt in range(max_retries + 1):
            resp = self.session.get(f"{SLACK_API}/{method}", params=params, timeout=30)
            data = resp.json()
            if data.get("ok"):
                return data
            if data.get("error") == "ratelimited" and attempt < max_retries:
                wait = int(resp.headers.get("Retry-After", "5"))
                print(f"  [rate limited on {method}, waiting {wait}s...]")
                time.sleep(wait)
                continue
            raise SlackError(f"{method} failed: {data.get('error')}")

    def resolve_channel_ids(self, channel_names):
        """Return {channel_name: channel_id} for names found across public
        and private channels the bot has been invited to."""
        wanted = {name.lower(): name for name in channel_names}
        found = {}
        cursor = None
        while True:
            params = {
                "types": "public_channel,private_channel",
                "limit": 200,
                "exclude_archived": "false",
            }
            if cursor:
                params["cursor"] = cursor
            data = self._get("conversations.list", params)
            for ch in data.get("channels", []):
                name = ch["name"].lower()
                if name in wanted and wanted[name] not in found:
                    found[wanted[name]] = ch["id"]
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor or len(found) == len(wanted):
                break
        missing = set(wanted.values()) - set(found.keys())
        if missing:
            print(f"[warn] channels not found or bot not invited: {sorted(missing)}")
        return found

    def fetch_history(self, channel_id, oldest_ts):
        """All messages in a channel since oldest_ts (unix seconds), newest last."""
        messages = []
        cursor = None
        while True:
            params = {"channel": channel_id, "oldest": oldest_ts, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = self._get("conversations.history", params)
            messages.extend(data.get("messages", []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.3)  # stay under Slack's tier-3 rate limit
        messages.reverse()
        return messages

    def fetch_thread_replies(self, channel_id, thread_ts):
        data = self._get(
            "conversations.replies", {"channel": channel_id, "ts": thread_ts, "limit": 200}
        )
        return data.get("messages", [])[1:]  # drop the parent, already have it

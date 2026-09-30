"""Roll individual analyzed alerts up into dashboard-level summary stats."""

from collections import Counter, defaultdict


def summarize(alerts):
    total = len(alerts)
    by_env = Counter(a["env"] for a in alerts)
    by_category = Counter(a["analysis"]["category"] for a in alerts)
    by_severity = Counter(a["analysis"]["severity"] for a in alerts)
    by_channel = Counter(a["channel"] for a in alerts)

    pod_restarts = sum(1 for a in alerts if a["analysis"].get("pod_restart"))

    by_component = Counter(a["analysis"]["component"] for a in alerts)
    recurring = [
        {"component": comp, "count": count}
        for comp, count in by_component.most_common(10)
        if count > 1
    ]

    by_day = defaultdict(int)
    for a in alerts:
        day = a["timestamp"][:10]  # ISO date prefix
        by_day[day] += 1

    return {
        "total": total,
        "by_env": dict(by_env),
        "by_category": dict(by_category),
        "by_severity": dict(by_severity),
        "by_channel": dict(by_channel),
        "pod_restarts": pod_restarts,
        "recurring_components": recurring,
        "by_day": dict(sorted(by_day.items())),
    }

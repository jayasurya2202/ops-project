"""Send each raw alert (with its embedded logs/metrics) to Claude and get
back a structured classification + root cause + suggested fix."""

import json
import anthropic

MODEL = "claude-sonnet-5"

ANALYSIS_TOOL = {
    "name": "report_alert_analysis",
    "description": "Structured analysis of one infra/pod/process alert.",
    "input_schema": {
        "type": "object",
        "properties": {
            "env": {
                "type": "string",
                "enum": ["prod", "uat", "qa", "shared"],
                "description": (
                    "The real environment this alert is about, parsed from the alert "
                    "message itself (alerts typically start with or clearly state PROD/"
                    "UAT/QA). Use the channel's default environment only as a fallback "
                    "when the message truly doesn't indicate one; use 'shared' only then."
                ),
            },
            "category": {
                "type": "string",
                "enum": ["infra", "pod", "process"],
                "description": "What layer this alert is actually about, based on its content.",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "warning", "info"],
            },
            "pod_restart": {
                "type": "boolean",
                "description": (
                    "True only if this alert describes an actual Kubernetes pod/container "
                    "restart, crash loop (e.g. CrashLoopBackOff), OOMKill-triggered restart, "
                    "or an eviction that caused a reschedule/recreate. False for pod alerts "
                    "that are merely pending, degraded, or unhealthy without an actual "
                    "restart/recreate event, and false for non-pod alerts."
                ),
            },
            "component": {
                "type": "string",
                "description": "Short name of the affected system, e.g. 'postgres-primary', 'checkout-pod', 'airflow-dag:daily_etl'.",
            },
            "k8s_namespace": {
                "type": "string",
                "description": "Kubernetes namespace this alert relates to, if it is a k8s/pod alert. Omit or leave empty for non-k8s alerts.",
            },
            "k8s_pod": {
                "type": "string",
                "description": "Kubernetes pod name (or pod-name prefix / deployment name) this alert relates to, if applicable. Omit or leave empty for non-k8s alerts.",
            },
            "k8s_cluster": {
                "type": "string",
                "description": "Kubernetes cluster name this alert relates to, if applicable. Omit or leave empty for non-k8s alerts.",
            },
            "summary": {
                "type": "string",
                "description": "One or two sentences: what happened, in plain language.",
            },
            "root_cause": {
                "type": "string",
                "description": "Best-guess root cause inferred from the logs/metrics in the message.",
            },
            "solution": {
                "type": "string",
                "description": "Concrete, actionable remediation steps.",
            },
        },
        "required": ["env", "category", "severity", "pod_restart", "component", "summary", "root_cause", "solution"],
    },
}

SYSTEM_PROMPT = (
    "You are a DevOps SRE analyzing alert messages pulled from Slack alert channels. "
    "Each message may contain raw logs, metric values, stack traces, or alertmanager/"
    "signoz/kubernetes-event style payloads. Infer what actually broke, the most likely "
    "root cause, and a concrete fix. If the message lacks enough detail, say so plainly "
    "in root_cause rather than guessing wildly. When the alert is Kubernetes/pod related, "
    "also populate k8s_namespace, k8s_pod, and k8s_cluster from whatever the message "
    "contains. Alerts usually state their environment (PROD/UAT/QA) right at the start "
    "of the message — read that from the actual content rather than assuming it from "
    "the channel. Always call report_alert_analysis."
)


class Analyzer:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, alert_text, channel_name, default_env, default_category):
        prompt = (
            f"Channel: #{channel_name} (channel's default environment, only a "
            f"fallback if the message itself doesn't state one: {default_env})\n"
            f"Default category guess: {default_category}\n\n"
            f"Alert message:\n{alert_text}"
        )
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "report_alert_analysis"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "report_alert_analysis":
                return block.input
        raise RuntimeError(f"model did not return the expected tool call: {resp.content}")

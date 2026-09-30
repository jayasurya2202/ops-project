"""Render the aggregated alert data into one self-contained HTML dashboard.

Styling lives in dashboard.css and interactivity is driven by Alpine.js
(vendored in vendor/alpine.min.js) - both are inlined into the generated
HTML at render time so the output file stays fully self-contained and works
offline, with no build step and no CDN dependency at view time.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(HERE, "dashboard.css")
ALPINE_PATH = os.path.join(HERE, "vendor", "alpine.min.js")

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>DevOps Alert Dashboard</title>
<style>
__CSS__
</style>
</head>
<body x-data="dashboardApp()" x-cloak>
  <header class="topbar">
    <div>
      <h1>DevOps Alert Dashboard</h1>
      <p class="subtitle">__SUBTITLE__</p>
    </div>
    <div class="daterange">
      <div class="presets">
        <template x-for="p in presetKeys" :key="p">
          <button type="button" :class="{active: activePreset === p}" @click="setPreset(p)" x-text="presetLabels[p]"></button>
        </template>
      </div>
      <label>From <input type="datetime-local" x-model="dateFrom" @change="onManualDateChange()"></label>
      <label>To <input type="datetime-local" x-model="dateTo" @change="onManualDateChange()"></label>
      <button type="button" @click="clearDates()">Clear</button>
    </div>
  </header>

  <section class="tiles">
    <div class="tile"><div class="n" x-text="summary.total"></div><div class="l">Total alerts (<span x-text="rangeLabel"></span>)</div></div>
    <div class="tile tile-prod"><div class="n" x-text="summary.by_env.prod || 0"></div><div class="l">Prod</div></div>
    <div class="tile"><div class="n" x-text="summary.by_env.uat || 0"></div><div class="l">UAT</div></div>
    <div class="tile"><div class="n" x-text="summary.by_env.qa || 0"></div><div class="l">QA</div></div>
    <div class="tile"><div class="n" x-text="summary.by_env.shared || 0"></div><div class="l">Shared infra</div></div>
    <div class="tile tile-critical"><div class="n" x-text="summary.by_severity.critical || 0"></div><div class="l">Critical</div></div>
    <div class="tile tile-restart"><div class="n" x-text="summary.pod_restarts || 0"></div><div class="l">Pod restarts</div></div>
  </section>

  <section class="card">
    <h2>Prod pod restarts</h2>
    <template x-if="prodRestarts.length === 0"><div class="empty">No prod pod restarts in this window.</div></template>
    <template x-for="a in prodRestarts" :key="cardKey(a)"><div x-html="cardHtml(a, false)"></div></template>
  </section>

  <section class="card">
    <h2>Pod restarts (all environments)</h2>
    <template x-if="podRestarts.length === 0"><div class="empty">No pod restarts in this window.</div></template>
    <template x-for="a in podRestarts" :key="cardKey(a)"><div x-html="cardHtml(a, false)"></div></template>
  </section>

  <section class="card">
    <h2>Process alerts</h2>
    <template x-if="processAlerts.length === 0"><div class="empty">No process alerts in this window.</div></template>
    <template x-for="a in processAlerts" :key="cardKey(a)"><div x-html="cardHtml(a, false)"></div></template>
  </section>

  <section class="grid2">
    <div class="card">
      <h2>By category</h2>
      <template x-for="[label, count] in Object.entries(summary.by_category)" :key="label">
        <div class="barrow">
          <div class="label" x-text="label"></div>
          <div class="track"><div class="fill" :class="'cat-' + label" :style="{ width: barWidth(count, summary.by_category) + '%' }"></div></div>
          <div class="count" x-text="count"></div>
        </div>
      </template>
    </div>
    <div class="card">
      <h2>By severity</h2>
      <template x-for="[label, count] in Object.entries(summary.by_severity)" :key="label">
        <div class="barrow">
          <div class="label" x-text="label"></div>
          <div class="track"><div class="fill" :class="'sev-' + label" :style="{ width: barWidth(count, summary.by_severity) + '%' }"></div></div>
          <div class="count" x-text="count"></div>
        </div>
      </template>
    </div>
  </section>

  <section class="card">
    <h2>Recurring components (appeared more than once)</h2>
    <template x-if="summary.recurring_components.length === 0"><div class="empty">No component repeated more than once in this window.</div></template>
    <template x-for="r in summary.recurring_components" :key="r.component">
      <span class="chip" x-text="r.component + ' × ' + r.count"></span>
    </template>
  </section>

  <section class="card">
    <h2>Alerts by channel &mdash; click one to filter the list below</h2>
    <div class="channelgrid">
      <template x-for="[chan, count] in channelCounts" :key="chan">
        <button type="button" class="chanCard" :class="{active: activeChannel === chan}" @click="toggleChannel(chan)">
          <span x-text="'#' + chan"></span><span class="chanCount" x-text="count"></span>
        </button>
      </template>
    </div>
  </section>

  <div class="filters">
    <template x-for="k in filterKeys" :key="k">
      <button type="button" :class="{active: activeFilter === k}" @click="activeFilter = k" x-text="k"></button>
    </template>
  </div>

  <div class="channelbanner" x-show="activeChannel !== 'all'" x-cloak>
    <span>Showing only <strong x-text="'#' + activeChannel"></strong></span>
    <button type="button" @click="activeChannel = 'all'">Show all channels</button>
  </div>

  <div x-ref="alertList">
    <template x-if="visibleAlerts.length === 0"><div class="empty">No alerts match this filter.</div></template>
    <template x-for="a in visibleAlerts" :key="cardKey(a)"><div x-html="cardHtml(a, true)"></div></template>
  </div>

<script>
const DATA = __DATA_JSON__;

function dashboardApp() {
  return {
    alerts: DATA.alerts,
    dateFrom: '',
    dateTo: '',
    activePreset: null,
    activeFilter: 'all',
    activeChannel: 'all',
    filterKeys: ['all', 'infra', 'pod', 'process', 'critical', 'warning', 'info'],
    presetKeys: ['24h', '7d', '15d', 'all'],
    presetLabels: { '24h': 'Last 24h', '7d': 'Last 7 days', '15d': 'Last 15 days', all: 'All time' },
    envLabels: { prod: 'Prod', uat: 'UAT', qa: 'QA', shared: 'Shared infra' },
    severityRank: { critical: 0, warning: 1, info: 2 },
    envRank: { prod: 0, uat: 1, qa: 2, shared: 3 },

    escapeHtml(s) {
      return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },

    fmtTime(iso) {
      return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    },

    cardKey(a) {
      return a.channel + '|' + a.timestamp + '|' + a.analysis.component;
    },

    byUrgency(a, b) {
      const r = (this.severityRank[a.analysis.severity] ?? 9) - (this.severityRank[b.analysis.severity] ?? 9);
      if (r !== 0) return r;
      const e = (this.envRank[a.env] ?? 9) - (this.envRank[b.env] ?? 9);
      if (e !== 0) return e;
      return new Date(b.timestamp) - new Date(a.timestamp);
    },

    get dateFiltered() {
      const from = this.dateFrom ? new Date(this.dateFrom).getTime() : -Infinity;
      const to = this.dateTo ? new Date(this.dateTo).getTime() : Infinity;
      return this.alerts.filter(a => {
        const t = new Date(a.timestamp).getTime();
        return t >= from && t <= to;
      });
    },

    get summary() {
      const alerts = this.dateFiltered;
      const countBy = keyFn => alerts.reduce((acc, a) => {
        const k = keyFn(a);
        acc[k] = (acc[k] || 0) + 1;
        return acc;
      }, {});
      const byComponent = countBy(a => a.analysis.component);
      const recurring = Object.entries(byComponent)
        .filter(([, count]) => count > 1)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([component, count]) => ({ component, count }));
      return {
        total: alerts.length,
        by_env: countBy(a => a.env),
        by_category: countBy(a => a.analysis.category),
        by_severity: countBy(a => a.analysis.severity),
        pod_restarts: alerts.filter(a => a.analysis.pod_restart).length,
        recurring_components: recurring,
      };
    },

    get rangeLabel() {
      if (this.activePreset) return this.presetLabels[this.activePreset].toLowerCase();
      if (!this.dateFrom && !this.dateTo) return 'all time';
      return 'custom range';
    },

    get prodRestarts() {
      return this.dateFiltered.filter(a => a.analysis.pod_restart && a.env === 'prod').sort((a, b) => this.byUrgency(a, b));
    },
    get podRestarts() {
      return this.dateFiltered.filter(a => a.analysis.pod_restart).sort((a, b) => this.byUrgency(a, b));
    },
    get processAlerts() {
      return this.dateFiltered.filter(a => a.analysis.category === 'process').sort((a, b) => this.byUrgency(a, b));
    },

    get channelCounts() {
      const counts = {};
      this.dateFiltered.forEach(a => { counts[a.channel] = (counts[a.channel] || 0) + 1; });
      return Object.entries(counts).sort((a, b) => b[1] - a[1]);
    },

    get visibleAlerts() {
      return this.dateFiltered.filter(a =>
        (this.activeFilter === 'all' || a.analysis.category === this.activeFilter || a.analysis.severity === this.activeFilter) &&
        (this.activeChannel === 'all' || a.channel === this.activeChannel)
      ).sort((a, b) => this.byUrgency(a, b));
    },

    barWidth(count, counts) {
      const max = Math.max(1, ...Object.values(counts));
      return (count / max * 100).toFixed(0);
    },

    toLocalInputValue(d) {
      const pad = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },

    setPreset(key) {
      this.activePreset = key;
      const now = new Date();
      if (key === 'all') { this.dateFrom = ''; this.dateTo = ''; return; }
      const hoursByPreset = { '24h': 24, '7d': 24 * 7, '15d': 24 * 15 };
      const from = new Date(now.getTime() - hoursByPreset[key] * 3600 * 1000);
      this.dateFrom = this.toLocalInputValue(from);
      this.dateTo = this.toLocalInputValue(now);
    },

    clearDates() {
      this.dateFrom = '';
      this.dateTo = '';
      this.activePreset = null;
    },

    onManualDateChange() {
      this.activePreset = null;
    },

    toggleChannel(name) {
      this.activeChannel = this.activeChannel === name ? 'all' : name;
      this.$nextTick(() => this.$refs.alertList.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    },

    k8sLine(a) {
      const { k8s_namespace: ns, k8s_pod: pod, k8s_cluster: cluster } = a.analysis;
      const parts = [];
      if (ns) parts.push(`Namespace: ${this.escapeHtml(ns)}`);
      if (pod) parts.push(`Pod: ${this.escapeHtml(pod)}`);
      if (cluster) parts.push(`Cluster: ${this.escapeHtml(cluster)}`);
      return parts.join(' · ');
    },

    cardHtml(a, showCategoryBadge) {
      const esc = s => this.escapeHtml(s);
      const k8sLine = this.k8sLine(a);
      return `
        <details class="alert">
          <summary>
            <span class="badge sev-${a.analysis.severity}">${a.analysis.severity}</span>
            ${showCategoryBadge ? `<span class="badge cat-${a.analysis.category}">${a.analysis.category}</span>` : ''}
            <span class="ts">${this.fmtTime(a.timestamp)}</span>
            <span class="chan">#${esc(a.channel)}</span>
            <span class="comp">${esc(a.analysis.component)}</span>
            <span class="sum">${esc(a.analysis.summary)}</span>
          </summary>
          <div class="detail">
            <h4>Alert</h4><p>${esc(a.analysis.component)} <span class="chan">#${esc(a.channel)}</span></p>
            <h4>When</h4><p>${this.fmtTime(a.timestamp)}</p>
            <h4>Environment</h4><p>${this.envLabels[a.env] || esc(a.env)}</p>
            <h4>Summary</h4><p>${esc(a.analysis.summary)}</p>
            <h4>Root cause</h4><p>${esc(a.analysis.root_cause)}</p>
            <h4>Suggested solution</h4><p>${esc(a.analysis.solution)}</p>
            ${k8sLine ? `<h4>Kubernetes</h4><p>${k8sLine}</p>` : ''}
            <h4>Original message</h4><p class="rawmsg">${esc(a.raw_excerpt)}</p>
          </div>
        </details>`;
    },
  };
}
</script>
<script>
__ALPINE_JS__
</script>
</body>
</html>
"""


def escape_js_string_in_html(text):
    return text.replace("</script>", "<\\/script>")


def _read(path):
    with open(path) as f:
        return f.read()


def generate_html(alerts, summary, window_days, generated_at):
    payload = {
        "summary": summary,
        "alerts": alerts,
        "window_days": window_days,
    }
    if not window_days:
        window_label = "All time"
    elif window_days == 1:
        window_label = "Today"
    else:
        window_label = f"Last {window_days} days"
    html = TEMPLATE.replace("__SUBTITLE__", f"{window_label} · generated {generated_at}")
    html = html.replace("__DATA_JSON__", escape_js_string_in_html(json.dumps(payload)))
    html = html.replace("__CSS__", _read(CSS_PATH))
    html = html.replace("__ALPINE_JS__", escape_js_string_in_html(_read(ALPINE_PATH)))
    return html

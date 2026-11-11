const REFRESH_MS = 5000;
const MAIN = document.querySelector("main");
const STALE_MS = Number(MAIN.dataset.readingStaleSeconds) * 1000;
const CAN_VIEW_HISTORY = document.body.dataset.canViewHistory === "true";
const HAS_HISTORY_PANEL = CAN_VIEW_HISTORY && Boolean(document.getElementById("sensor"));
const DEFAULT_I18N = {
  locale: "sv", turbidity: "Turbiditet", temperature: "Temperatur", measurement: "Mätvärde",
  range_hour: "senaste timmen", range_day: "senaste dygnet", range_week: "senaste 7 dagarna",
  range_all: "senaste 200 mätningarna", fetch_error: "Mätvärdena kunde inte hämtas.",
  no_readings: "Inga mätvärden ännu.", latest_status: "Senaste status: ", anomaly: "Avvikelse",
  threshold: "gräns", stale: "Mätningen är inaktuell eller saknar giltig tid.",
  show_history: "Visa historik", show_history_for: "Visa historik för %(sensor)s",
  mixed_history: "Historiken innehåller olika mätstorheter och kan inte visas i samma diagram.",
  no_interval_readings: "Inga mätvärden finns för det valda intervallet.", threshold_label: "Gränsvärde",
  chart_explanation: "● OK · ▲ Avvikelse. Statusen följer projektets konfigurerade gränsregel och är inte en officiell bedömning av badvattnet.",
  time_local: "Tid (lokal tid)", value: "Värde",
  choose_both: "Välj både Från och Till, eller använd ett snabbval.",
  invalid_date: "Tidsintervallet innehåller ett ogiltigt datum.", from_before_to: "Från måste vara tidigare än Till.",
  interval: "Intervall: %(range)s.", custom_interval: "Eget intervall: %(start)s – %(end)s.",
  custom_incomplete: "Eget intervall är inte komplett.", choose_sensor: "Välj en sensor innan rapporten skapas.",
  session_expired: "Din session har gått ut eller saknar behörighet. Logga in igen för att visa historiken.",
  unavailable: "Mätvärdena är inte tillgängliga just nu.", updated: "Uppdaterad %(time)s",
  update_failed: "Uppdateringen misslyckades",
  refresh_error: "Kunde inte hämta nya mätvärden. Kontrollera anslutningen eller logga in igen. Ett nytt försök görs automatiskt.",
};
const i18nNode = document.getElementById("dashboard-i18n");
const I18N = i18nNode ? JSON.parse(i18nNode.textContent) : DEFAULT_I18N;
const t = (key, replacements = {}) => {
  let value = I18N[key] ?? DEFAULT_I18N[key] ?? key;
  for (const [name, replacement] of Object.entries(replacements)) {
    value = value.replace(`%(${name})s`, replacement);
  }
  return value;
};
const LOCALE = I18N.locale || DEFAULT_I18N.locale;
const LABELS = { turbidity: t("turbidity"), temperature: t("temperature") };
const RANGE_PRESETS = {
  hour: { hours: 1, label: t("range_hour") },
  day: { hours: 24, label: t("range_day") },
  week: { hours: 24 * 7, label: t("range_week") },
  all: { hours: null, label: t("range_all") },
};
const $ = (id) => document.getElementById(id);
let chart = null;
let selected = null;
let activeRange = "all";
let latestReadings = [];
let inFlight = false;         // förhindrar överlappande uppdateringar (issue #24)
let pendingRefresh = false;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    const error = new Error(t("fetch_error"));
    error.status = r.status;
    throw error;
  }
  return r.json();
}

const isAnomaly = (s) => s === "ANOMALY";
const fmt = (iso) => new Date(iso).toLocaleString(LOCALE);

function sensorDisplayName(sensorId) {
  return sensorId
    .replace(/-(turbidity|temperature)$/, "")
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function sensorMetricLabel(sensorId) {
  if (sensorId.endsWith("-turbidity")) return LABELS.turbidity;
  if (sensorId.endsWith("-temperature")) return LABELS.temperature;
  return t("measurement");
}

function sensorOptionLabel(sensorId) {
  return `${sensorDisplayName(sensorId)} – ${sensorMetricLabel(sensorId)}`;
}

// Bygger element med textContent. Data från API:t tolkas aldrig som HTML (issue #43).
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCards(items) {
  const container = $("cards");
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    container.append(el("p", "text-muted", t("no_readings")));
    return;
  }
  for (const r of items) {
    const anomaly = isAnomaly(r.status);
    const measuredAt = Date.parse(r.timestamp);
    const stale = !Number.isFinite(measuredAt) || Date.now() - measuredAt > STALE_MS;
    const col = el("div", "col-md-6 col-xl-4");
    const card = el("div", `card shadow-sm h-100 border-${stale ? "warning" : anomaly ? "danger" : "success"}${r.sensor_id === selected ? " border-3" : ""}`);
    card.dataset.sensor = r.sensor_id;

    const body = el("div", "card-body");
    const value = el("div", "display-5 fw-bold");
    value.append(Number(r.value).toFixed(1), " ", el("small", "fs-6", r.unit));
    body.append(
      el("h3", "h5 mb-1", sensorDisplayName(r.sensor_id)),
      el("div", "text-muted small", `${LABELS[r.metric] || r.metric} · ${r.sensor_id}`),
      value,
      el(
        "span",
        `badge fs-6 d-inline-block text-wrap text-start mw-100 bg-${stale ? "secondary" : anomaly ? "danger" : "success"}`,
        `${stale ? t("latest_status") : ""}${anomaly ? `⚠ ${t("anomaly")}` : "✔ OK"}`),
      el("div", "text-muted small mt-2", `${fmt(r.timestamp)} · ${t("threshold")} ${r.threshold ?? "–"} ${r.unit}`),
    );
    if (stale) body.append(el("div", "text-warning fw-bold mt-2", t("stale")));
    card.append(body);
    col.append(card);
    container.append(col);

    if (CAN_VIEW_HISTORY) {
      const link = el("a", "stretched-link", t("show_history"));
      link.setAttribute("aria-label", t("show_history_for", { sensor: sensorOptionLabel(r.sensor_id) }));
      link.href = `${MAIN.dataset.historyUrl}?sensor_id=${encodeURIComponent(r.sensor_id)}`;
      body.append(link);
    }
  }
}

function renderChart(data) {
  const rows = data.results;
  const mixed = rows.length > 0 && data.metric == null;
  const message = $("history-message");
  const explanation = $("chart-explanation");
  message.textContent = mixed ? t("mixed_history") :
    rows.length ? "" : t("no_interval_readings");
  message.className = mixed ? "alert alert-warning" : "text-muted";
  $("chart").hidden = mixed || !rows.length;
  explanation.hidden = mixed || !rows.length;
  if (mixed || !rows.length) {
    if (chart) { chart.destroy(); chart = null; }
    return;
  }
  const name = `${LABELS[data.metric] || t("value")} (${data.unit || ""})`;
  const points = rows.map((r) => ({ x: Date.parse(r.timestamp), y: r.value, status: r.status }));
  const dense = rows.length > 60;
  const datasets = [
    { label: name, data: points, borderColor: "#0d6efd", tension: 0.2,
      pointBackgroundColor: rows.map((r) => (isAnomaly(r.status) ? "#dc3545" : "#198754")),
      pointStyle: rows.map((r) => (isAnomaly(r.status) ? "triangle" : "circle")),
      pointRadius: rows.map((r) => (isAnomaly(r.status) ? 5 : dense ? 0 : 3)),
      pointHoverRadius: 6 },
  ];
  if (data.threshold != null) {
    datasets.push({ label: t("threshold_label"), data: points.map((point) => ({ x: point.x, y: data.threshold })), borderColor: "#dc3545",
      borderDash: [6, 4], pointRadius: 0 });
  }
  const cfg = { datasets };
  explanation.textContent = t("chart_explanation");
  const options = { responsive: true, maintainAspectRatio: false, animation: false, parsing: false, plugins: { tooltip: { callbacks: {
    title: (items) => items.length ? fmt(items[0].parsed.x) : "",
    label: (item) => item.datasetIndex === 0
      ? `${name}: ${item.parsed.y} ${data.unit || ""} · ${isAnomaly(item.raw.status) ? `⚠ ${t("anomaly")}` : "✔ OK"}`
      : `${t("threshold_label")}: ${item.parsed.y} ${data.unit || ""}`,
  } } }, scales: {
    x: { type: "linear", title: { display: true, text: t("time_local") }, ticks: {
      maxTicksLimit: 3, minRotation: 0, maxRotation: 0,
      callback: (value) => new Date(value).toLocaleString(LOCALE, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
    } },
    y: { title: { display: true, text: data.unit ? `${t("value")} (${data.unit})` : t("value") } },
  } };
  if (chart) {
    chart.data = cfg;
    chart.options = options;
    chart.update("none");
  } else chart = new Chart($("chart"), { type: "line", data: cfg, options });
}

function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function validateRange(fromValue, toValue) {
  if (!fromValue && !toValue) return { valid: true, start: null, end: null };
  if (!fromValue || !toValue) return { valid: false, message: t("choose_both") };
  const start = new Date(fromValue);
  const end = new Date(toValue);
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
    return { valid: false, message: t("invalid_date") };
  }
  if (start >= end) return { valid: false, message: t("from_before_to") };
  return { valid: true, start, end };
}

function markActiveRange() {
  document.querySelectorAll(".range-preset").forEach((button) => {
    const active = button.dataset.range === activeRange;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function updateRangeInputs(now = new Date()) {
  const preset = RANGE_PRESETS[activeRange];
  if (!preset) return;
  if (preset.hours == null) {
    $("from").value = "";
    $("to").value = "";
    return;
  }
  $("to").value = toLocalInput(now);
  $("from").value = toLocalInput(new Date(now.getTime() - preset.hours * 60 * 60 * 1000));
}

function updateIntervalSummary(range) {
  const summary = $("interval-summary");
  if (activeRange && RANGE_PRESETS[activeRange]) {
    summary.textContent = t("interval", { range: RANGE_PRESETS[activeRange].label });
    return;
  }
  summary.textContent = range.valid && range.start
    ? t("custom_interval", { start: fmt(range.start.toISOString()), end: fmt(range.end.toISOString()) })
    : t("custom_incomplete");
}

function historyUrl() {
  if (activeRange) updateRangeInputs();
  const range = validateRange($("from").value, $("to").value);
  updateIntervalSummary(range);
  if (!range.valid) return { error: range.message };
  const p = new URLSearchParams({ sensor_id: selected, limit: 200 });
  if (range.start) p.set("start", range.start.toISOString());
  if (range.end) p.set("end", range.end.toISOString());
  return { url: `/api/readings/?${p}` };
}

function reportUrl() {
  if (!selected) {
    return { error: t("choose_sensor") };
  }

  if (activeRange) updateRangeInputs();

  const range = validateRange($("from").value, $("to").value);
  updateIntervalSummary(range);

  if (!range.valid) {
    return { error: range.message };
  }

  const params = new URLSearchParams({ sensor_id: selected });

  if (range.start) params.set("start", range.start.toISOString());
  if (range.end) params.set("end", range.end.toISOString());

  return {
    url: `/api/reports/history.pdf?${params}`,
  };
}

function renderRangeError(message) {
  $("history-message").textContent = message;
  $("history-message").className = "alert alert-warning";
  $("chart").hidden = true;
  $("chart-explanation").hidden = true;
  if (chart) { chart.destroy(); chart = null; }
}

function renderSensorOptions(sensors) {
  const sel = $("sensor");
  const current = Array.from(sel.options).map((o) => o.value).join("|");
  if (current !== sensors.join("|")) {
    sel.replaceChildren(...sensors.map((s) => { const o = el("option", "", sensorOptionLabel(s)); o.value = s; return o; }));
  }
}

async function refresh() {
  if (inFlight) { pendingRefresh = true; return; }   // kör om direkt efter pågående anrop
  inFlight = true;
  try {
    if (HAS_HISTORY_PANEL) {
      const sensors = (await getJSON("/api/sensors/")).results;
      renderSensorOptions(sensors);
      if (!selected && sensors.length) {
        const requested = new URLSearchParams(window.location.search || "").get("sensor_id");
        selected = sensors.includes(requested) ? requested : sensors[0];
      }
      if (selected) $("sensor").value = selected;
    }
    latestReadings = (await getJSON("/api/readings/latest/")).results;
    renderCards(latestReadings);
    const summary = {
      "summary-total": latestReadings.length,
      "summary-anomaly": latestReadings.filter((r) => isAnomaly(r.status)).length,
      "summary-stale": latestReadings.filter((r) => !Number.isFinite(Date.parse(r.timestamp)) || Date.now() - Date.parse(r.timestamp) > STALE_MS).length,
    };
    for (const [id, count] of Object.entries(summary)) {
      if ($(id)) $(id).textContent = String(count);
    }
    if (HAS_HISTORY_PANEL && selected) {
      const history = historyUrl();
      if (history.error) renderRangeError(history.error);
      else renderChart(await getJSON(history.url));
    }
    $("updated").textContent = t("updated", { time: new Date().toLocaleTimeString(LOCALE) });
    $("error").classList.add("d-none");
  } catch (e) {
    if (HAS_HISTORY_PANEL && (e.status === 401 || e.status === 403)) {
      renderRangeError(t("session_expired"));
    }
    if (latestReadings.length) renderCards(latestReadings);
    else if ($("cards")) $("cards").replaceChildren(el("p", "text-muted", t("unavailable")));
    $("updated").textContent = t("update_failed");
    $("error").textContent = t("refresh_error");
    $("error").classList.remove("d-none");
  } finally {
    inFlight = false;
    if (pendingRefresh) { pendingRefresh = false; refresh(); }
  }
}

if (HAS_HISTORY_PANEL) {
  window.addEventListener("resize", () => {
    requestAnimationFrame(() => {
      if (chart) chart.resize();
    });
  });
  $("sensor").addEventListener("change", (e) => { selected = e.target.value; refresh(); });
  $("apply").addEventListener("click", refresh);
  $("download-pdf").addEventListener("click", () => {
    const report = reportUrl();

    if (report.error) {
      renderRangeError(report.error);
      return;
    }

    window.location.assign(report.url);
  });
  for (const id of ["from", "to"]) {
    $(id).addEventListener("input", () => { activeRange = null; markActiveRange(); });
  }
  document.querySelectorAll(".range-preset").forEach((button) => {
    button.addEventListener("click", () => {
      activeRange = button.dataset.range;
      markActiveRange();
      updateRangeInputs();
      refresh();
    });
  });
  $("reset").addEventListener("click", () => {
    activeRange = "all";
    markActiveRange();
    updateRangeInputs();
    refresh();
  });
}
refresh();
setInterval(refresh, REFRESH_MS);

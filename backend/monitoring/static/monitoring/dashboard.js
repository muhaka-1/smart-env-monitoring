const REFRESH_MS = 5000;
const STALE_MS = Number(document.querySelector("main").dataset.readingStaleSeconds) * 1000;
const LABELS = { turbidity: "Turbiditet", temperature: "Temperatur" };
const RANGE_PRESETS = {
  hour: { hours: 1, label: "senaste timmen" },
  day: { hours: 24, label: "senaste dygnet" },
  week: { hours: 24 * 7, label: "senaste 7 dagarna" },
  all: { hours: null, label: "all historik" },
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
  if (!r.ok) throw new Error(`${url} -> HTTP ${r.status}`);
  return r.json();
}

const isAnomaly = (s) => s === "ANOMALY";
const fmt = (iso) => new Date(iso).toLocaleString("sv-SE");

// Bygger element med textContent. Data från API:t tolkas aldrig som HTML (issue #43).
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCards(items) {
  const container = $("cards");
  container.replaceChildren();
  if (!items.length) {
    container.append(el("p", "text-muted", "Inga mätvärden ännu."));
    return;
  }
  for (const r of items) {
    const anomaly = isAnomaly(r.status);
    const measuredAt = Date.parse(r.timestamp);
    const stale = !Number.isFinite(measuredAt) || Date.now() - measuredAt > STALE_MS;
    const col = el("div", "col-md-6 col-xl-4");
    const card = el("div", `card shadow-sm h-100 border-${stale ? "warning" : anomaly ? "danger" : "success"}${r.sensor_id === selected ? " border-3" : ""}`);
    card.setAttribute("role", "button");
    card.dataset.sensor = r.sensor_id;

    const body = el("div", "card-body");
    const value = el("div", "display-5 fw-bold");
    value.append(Number(r.value).toFixed(1), " ", el("small", "fs-6", r.unit));
    body.append(
      el("div", "fw-semibold", LABELS[r.metric] || r.metric),
      el("div", "text-muted small", r.sensor_id),
      value,
      el(
        "span",
        `badge fs-6 d-inline-block text-wrap text-start mw-100 bg-${stale ? "secondary" : anomaly ? "danger" : "success"}`,
        `${stale ? "Senaste status: " : ""}${anomaly ? "⚠ Avvikelse" : "✔ OK"}`),
      el("div", "text-muted small mt-2", `${fmt(r.timestamp)} · gräns ${r.threshold ?? "–"} ${r.unit}`),
    );
    if (stale) body.append(el("div", "text-warning fw-bold mt-2", "Mätningen är inaktuell eller saknar giltig tid."));
    card.append(body);
    col.append(card);
    container.append(col);

    card.addEventListener("click", () => {
      selected = r.sensor_id;
      $("sensor").value = selected;
      refresh();
    });
  }
}

function renderChart(data) {
  const rows = data.results;
  const mixed = rows.length > 0 && data.metric == null;
  const message = $("history-message");
  const explanation = $("chart-explanation");
  message.textContent = mixed ? "Historiken innehåller olika mätstorheter och kan inte visas i samma diagram." :
    rows.length ? "" : "Inga mätvärden finns för det valda intervallet.";
  message.className = mixed ? "alert alert-warning" : "text-muted";
  $("chart").hidden = mixed || !rows.length;
  explanation.hidden = mixed || !rows.length;
  if (mixed || !rows.length) {
    if (chart) { chart.destroy(); chart = null; }
    return;
  }
  const name = `${LABELS[data.metric] || "Värde"} (${data.unit || ""})`;
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
    datasets.push({ label: "Gränsvärde", data: points.map((point) => ({ x: point.x, y: data.threshold })), borderColor: "#dc3545",
      borderDash: [6, 4], pointRadius: 0 });
  }
  const cfg = { datasets };
  explanation.textContent = "● OK · ▲ Avvikelse. Statusen följer projektets konfigurerade gränsregel och är inte en officiell bedömning av badvattnet.";
  const options = { animation: false, parsing: false, plugins: { tooltip: { callbacks: {
    title: (items) => items.length ? fmt(items[0].parsed.x) : "",
    label: (item) => item.datasetIndex === 0
      ? `${name}: ${item.parsed.y} ${data.unit || ""} · ${isAnomaly(item.raw.status) ? "⚠ Avvikelse" : "✔ OK"}`
      : `Gränsvärde: ${item.parsed.y} ${data.unit || ""}`,
  } } }, scales: {
    x: { type: "linear", title: { display: true, text: "Tid (lokal tid)" }, ticks: {
      maxTicksLimit: 3, minRotation: 0, maxRotation: 0,
      callback: (value) => new Date(value).toLocaleString("sv-SE", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
    } },
    y: { title: { display: true, text: data.unit ? `Värde (${data.unit})` : "Värde" } },
  } };
  if (chart) { chart.data = cfg; chart.update("none"); }
  else chart = new Chart($("chart"), { type: "line", data: cfg, options });
}

function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function validateRange(fromValue, toValue) {
  if (!fromValue && !toValue) return { valid: true, start: null, end: null };
  if (!fromValue || !toValue) return { valid: false, message: "Välj både Från och Till, eller använd ett snabbval." };
  const start = new Date(fromValue);
  const end = new Date(toValue);
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
    return { valid: false, message: "Tidsintervallet innehåller ett ogiltigt datum." };
  }
  if (start >= end) return { valid: false, message: "Från måste vara tidigare än Till." };
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
    summary.textContent = `Intervall: ${RANGE_PRESETS[activeRange].label}${activeRange === "all" ? ", högst 200 mätningar" : ""}.`;
    return;
  }
  summary.textContent = range.valid && range.start
    ? `Eget intervall: ${fmt(range.start.toISOString())} – ${fmt(range.end.toISOString())}.`
    : "Eget intervall är inte komplett.";
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
    sel.replaceChildren(...sensors.map((s) => { const o = el("option", "", s); o.value = s; return o; }));
  }
}

async function refresh() {
  if (inFlight) { pendingRefresh = true; return; }   // kör om direkt efter pågående anrop
  inFlight = true;
  try {
    const sensors = (await getJSON("/api/sensors/")).results;
    renderSensorOptions(sensors);
    if (!selected && sensors.length) selected = sensors[0];
    if (selected) $("sensor").value = selected;
    latestReadings = (await getJSON("/api/readings/latest/")).results;
    renderCards(latestReadings);
    if (selected) {
      const history = historyUrl();
      if (history.error) renderRangeError(history.error);
      else renderChart(await getJSON(history.url));
    }
    $("updated").textContent = "Uppdaterad " + new Date().toLocaleTimeString("sv-SE");
    $("error").classList.add("d-none");
  } catch (e) {
    if (latestReadings.length) renderCards(latestReadings);
    $("error").textContent = "Kunde inte hämta data: " + e.message;
    $("error").classList.remove("d-none");
  } finally {
    inFlight = false;
    if (pendingRefresh) { pendingRefresh = false; refresh(); }
  }
}

$("sensor").addEventListener("change", (e) => { selected = e.target.value; refresh(); });
$("apply").addEventListener("click", refresh);
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
refresh();
setInterval(refresh, REFRESH_MS);

const REFRESH_MS = 5000;
const LABELS = { turbidity: "Turbiditet", temperature: "Temperatur" };
const $ = (id) => document.getElementById(id);
let chart = null;
let selected = null;
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
    const col = el("div", "col-md-4");
    const card = el("div", `card shadow-sm h-100 border-${anomaly ? "danger" : "success"}${r.sensor_id === selected ? " border-3" : ""}`);
    card.setAttribute("role", "button");
    card.dataset.sensor = r.sensor_id;

    const body = el("div", "card-body");
    const value = el("div", "display-5 fw-bold");
    value.append(Number(r.value).toFixed(1), " ", el("small", "fs-6", r.unit));
    body.append(
      el("div", "fw-semibold", LABELS[r.metric] || r.metric),
      el("div", "text-muted small", r.sensor_id),
      value,
      el("span", `badge fs-6 bg-${anomaly ? "danger" : "success"}`, anomaly ? "⚠ Avvikelse" : "✔ OK"),
      el("div", "text-muted small mt-2", `${fmt(r.timestamp)} · gräns ${r.threshold ?? "–"} ${r.unit}`),
    );
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
  const name = `${LABELS[data.metric] || "Värde"} (${data.unit || ""})`;
  const datasets = [
    { label: name, data: rows.map((r) => r.value), borderColor: "#0d6efd", tension: 0.2,
      pointBackgroundColor: rows.map((r) => (isAnomaly(r.status) ? "#dc3545" : "#198754")), pointRadius: 3 },
  ];
  if (data.threshold != null) {
    datasets.push({ label: "Gränsvärde", data: rows.map(() => data.threshold), borderColor: "#dc3545",
      borderDash: [6, 4], pointRadius: 0 });
  }
  const cfg = { labels: rows.map((r) => fmt(r.timestamp)), datasets };
  if (chart) { chart.data = cfg; chart.update("none"); }
  else chart = new Chart($("chart"), { type: "line", data: cfg, options: { animation: false } });
}

function historyUrl() {
  const p = new URLSearchParams({ sensor_id: selected, limit: 200 });
  if ($("from").value) p.set("start", new Date($("from").value).toISOString());
  if ($("to").value) p.set("end", new Date($("to").value).toISOString());
  return `/api/readings/?${p}`;
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
    renderCards((await getJSON("/api/readings/latest/")).results);
    if (selected) renderChart(await getJSON(historyUrl()));
    $("updated").textContent = "Uppdaterad " + new Date().toLocaleTimeString("sv-SE");
    $("error").classList.add("d-none");
  } catch (e) {
    $("error").textContent = "Kunde inte hämta data: " + e.message;
    $("error").classList.remove("d-none");
  } finally {
    inFlight = false;
    if (pendingRefresh) { pendingRefresh = false; refresh(); }
  }
}

$("sensor").addEventListener("change", (e) => { selected = e.target.value; refresh(); });
$("apply").addEventListener("click", refresh);
$("reset").addEventListener("click", () => { $("from").value = ""; $("to").value = ""; refresh(); });
refresh();
setInterval(refresh, REFRESH_MS);

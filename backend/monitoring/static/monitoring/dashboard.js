const REFRESH_MS = 5000;
const LABELS = { turbidity: "Turbiditet", temperature: "Temperatur" };
const $ = (id) => document.getElementById(id);
let chart = null;
let selected = null;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> HTTP ${r.status}`);
  return r.json();
}

const isAnomaly = (s) => s === "ANOMALY";
const fmt = (iso) => new Date(iso).toLocaleString("sv-SE");

function renderCards(items) {
  $("cards").innerHTML = items.map((r) => `
    <div class="col-md-4">
      <div class="card shadow-sm h-100 border-${isAnomaly(r.status) ? "danger" : "success"} ${r.sensor_id === selected ? "border-3" : ""}"
           role="button" data-sensor="${r.sensor_id}">
        <div class="card-body">
          <div class="fw-semibold">${LABELS[r.metric] || r.metric}</div>
          <div class="text-muted small">${r.sensor_id}</div>
          <div class="display-5 fw-bold">${r.value.toFixed(1)} <small class="fs-6">${r.unit}</small></div>
          <span class="badge fs-6 bg-${isAnomaly(r.status) ? "danger" : "success"}">
            ${isAnomaly(r.status) ? "⚠ Avvikelse" : "✔ OK"}</span>
          <div class="text-muted small mt-2">${fmt(r.timestamp)} · gräns ${r.threshold ?? "–"} ${r.unit}</div>
        </div>
      </div>
    </div>`).join("") || '<p class="text-muted">Inga mätvärden ännu.</p>';
  document.querySelectorAll("[data-sensor]").forEach((el) =>
    el.addEventListener("click", () => { selected = el.dataset.sensor; $("sensor").value = selected; refresh(); }));
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

async function refresh() {
  try {
    const sensors = (await getJSON("/api/sensors/")).results;
    const sel = $("sensor");
    if (sel.options.length !== sensors.length) {
      sel.innerHTML = sensors.map((s) => `<option>${s}</option>`).join("");
    }
    if (!selected && sensors.length) selected = sensors[0];
    if (selected) sel.value = selected;
    renderCards((await getJSON("/api/readings/latest/")).results);
    if (selected) renderChart(await getJSON(historyUrl()));
    $("updated").textContent = "Uppdaterad " + new Date().toLocaleTimeString("sv-SE");
    $("error").classList.add("d-none");
  } catch (e) {
    $("error").textContent = "Kunde inte hämta data: " + e.message;
    $("error").classList.remove("d-none");
  }
}

$("sensor").addEventListener("change", (e) => { selected = e.target.value; refresh(); });
$("apply").addEventListener("click", refresh);
$("reset").addEventListener("click", () => { $("from").value = ""; $("to").value = ""; refresh(); });
refresh();
setInterval(refresh, REFRESH_MS);

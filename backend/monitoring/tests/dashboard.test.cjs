const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Chart = require("../static/monitoring/vendor/chart.umd.min.js");

class Element {
  constructor() {
    this.children = []; this.dataset = {}; this.hidden = false; this.textContent = ""; this.value = "";
    this.className = "";
    this.classList = { toggle: () => {}, add: () => {}, remove: () => {} };
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute() {}
  addEventListener() {}
  get options() { return this.children; }
}
class ChartMock {
  constructor(canvas, config) { this.data = config.data; this.options = config.options; }
  resize() { this.resizeCount = (this.resizeCount || 0) + 1; }
  update() {}
  destroy() {}
}
const elements = {
  cards: new Element(), chart: new Element(), "history-message": new Element(),
  "chart-explanation": new Element(), "interval-summary": new Element(),
  from: new Element(), to: new Element(), sensor: new Element(),
};
const main = new Element();
main.dataset.readingStaleSeconds = "300";
const body = new Element();
body.dataset.canViewHistory = "true";
const document = {
  body,
  querySelector: () => main,
  querySelectorAll: () => [],
  getElementById: (id) => elements[id],
  createElement: () => new Element(),
};
const source = fs.readFileSync(path.join(__dirname, "../static/monitoring/dashboard.js"), "utf8");
const initIndex = source.lastIndexOf("if (HAS_HISTORY_PANEL) {");
assert.notEqual(initIndex, -1);
const context = vm.createContext({ document, Chart: ChartMock, Date, Number, Set, URLSearchParams });
vm.runInContext(source.slice(0, initIndex) + "\nglobalThis.dashboard = { renderCards, renderChart, renderSensorOptions, sensorDisplayName, sensorOptionLabel, validateRange };", context);

const now = Date.now();
const reading = { metric: "turbidity", unit: "NTU", value: 2, status: "OK", threshold: 30 };
context.dashboard.renderCards([
  { ...reading, sensor_id: "fresh", timestamp: new Date(now - 1000).toISOString() },
  { ...reading, sensor_id: "old", timestamp: new Date(now - 301000).toISOString() },
]);
const text = (element) => typeof element === "string" ? element : element.textContent + element.children.map(text).join("");
assert.doesNotMatch(text(elements.cards.children[0]), /inaktuell/);
assert.match(text(elements.cards.children[1]), /inaktuell/);

assert.equal(context.dashboard.sensorDisplayName("63rd-street-beach-turbidity"), "63rd Street Beach");
assert.equal(context.dashboard.sensorOptionLabel("oak-street-beach-temperature"), "Oak Street Beach – Temperatur");
context.dashboard.renderCards([
  { ...reading, sensor_id: "oak-street-beach-turbidity", timestamp: new Date(now - 1000).toISOString() },
]);
assert.match(text(elements.cards.children[0]), /Oak Street Beach/);
assert.match(text(elements.cards.children[0]), /Turbiditet/);
context.dashboard.renderSensorOptions(["oak-street-beach-temperature"]);
assert.equal(elements.sensor.options[0].value, "oak-street-beach-temperature");
assert.equal(elements.sensor.options[0].textContent, "Oak Street Beach – Temperatur");

const rows = [0, 1, 4].map((hour) => ({ ...reading, timestamp: new Date(Date.UTC(2026, 0, 1, hour)).toISOString() }));
context.dashboard.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: rows });
const chart = vm.runInContext("chart", context);
assert.equal(chart.options.scales.x.type, "linear");
assert.equal(chart.options.scales.x.title.text, "Tid (lokal tid)");
assert.equal(chart.options.scales.y.title.text, "Värde (NTU)");
const times = chart.data.datasets[0].data.map((point) => point.x);
assert.equal(times[2] - times[1], 3 * (times[1] - times[0]));
context.dashboard.renderChart({ metric: "temperature", unit: "°C", threshold: 25, results: rows });
assert.equal(chart.options.scales.y.title.text, "Värde (°C)");
const switchedTooltipLabel = chart.options.plugins.tooltip.callbacks.label;
assert.match(
  switchedTooltipLabel({ datasetIndex: 0, parsed: { y: 22 }, raw: chart.data.datasets[0].data[0] }),
  /Temperatur \(°C\): 22 °C/
);
const tooltipTitle = chart.options.plugins?.tooltip?.callbacks?.title || Chart.Tooltip.defaults.callbacks.title;
const scale = { chart: { options: { locale: "sv-SE" } }, options: { ticks: { format: {} } } };
for (const dataset of chart.data.datasets) {
  for (const point of [dataset.data[0], dataset.data[2]]) {
    const item = {
      parsed: point,
      label: Chart.LinearScale.prototype.getLabelForValue.call(scale, point.x),
      chart: { data: chart.data },
      dataIndex: dataset.data.indexOf(point),
    };
    assert.equal(tooltipTitle.call({ options: {} }, [item]), new Date(point.x).toLocaleString("sv-SE"));
  }
}
assert.equal(tooltipTitle.call({ options: {} }, []), "");
context.dashboard.renderChart({ metric: null, unit: null, threshold: null, results: rows });
assert.equal(elements.chart.hidden, true);
assert.match(elements["history-message"].textContent, /olika mätstorheter/);
context.dashboard.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: rows });
assert.equal(elements.chart.hidden, false);
assert.equal(elements["history-message"].textContent, "");

const anomalyRows = [
  { ...reading, status: "OK", timestamp: new Date(Date.UTC(2026, 0, 1, 0)).toISOString() },
  { ...reading, status: "ANOMALY", value: 55, timestamp: new Date(Date.UTC(2026, 0, 1, 1)).toISOString() },
];
context.dashboard.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: anomalyRows });
const anomalyChart = vm.runInContext("chart", context);
assert.deepEqual(Array.from(anomalyChart.data.datasets[0].pointStyle), ["circle", "triangle"]);
const tooltipLabel = anomalyChart.options.plugins.tooltip.callbacks.label;
assert.match(tooltipLabel({ datasetIndex: 0, dataset: anomalyChart.data.datasets[0], parsed: { y: 55 }, raw: anomalyChart.data.datasets[0].data[1] }), /Avvikelse/);
assert.match(elements["chart-explanation"].textContent, /projektets konfigurerade gränsregel/);

context.dashboard.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: [] });
assert.equal(elements.chart.hidden, true);
assert.match(elements["history-message"].textContent, /Inga mätvärden/);

const publicElements = {
  cards: new Element(), error: new Element(), updated: new Element(),
};
const publicMain = new Element();
publicMain.dataset.readingStaleSeconds = "300";
const publicBody = new Element();
publicBody.dataset.canViewHistory = "false";
const publicCalls = [];
const publicDocument = {
  body: publicBody,
  querySelector: () => publicMain,
  querySelectorAll: () => [],
  getElementById: (id) => publicElements[id],
  createElement: () => new Element(),
};
const publicSource = source.replace(
  /refresh\(\);\r?\nsetInterval\(refresh, REFRESH_MS\);\s*$/,
  "globalThis.publicRefresh = refresh();"
);
const publicContext = vm.createContext({
  document: publicDocument,
  Chart: ChartMock,
  Date,
  Number,
  Set,
  URLSearchParams,
  setInterval: () => {},
  fetch: async (url) => {
    publicCalls.push(url);
    return { ok: true, json: async () => ({ results: [] }) };
  },
});

(async () => {
  vm.runInContext(publicSource, publicContext);
  await publicContext.publicRefresh;
  assert.deepEqual(publicCalls, ["/api/readings/latest/"]);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

assert.equal(context.dashboard.validateRange("", "").valid, true);
assert.equal(context.dashboard.validateRange("2026-01-01T10:00", "").valid, false);
assert.match(context.dashboard.validateRange("2026-01-01T11:00", "2026-01-01T10:00").message, /tidigare/);
assert.equal(context.dashboard.validateRange("2026-01-01T10:00", "2026-01-01T11:00").valid, true);

console.log("Dashboard labels, status, intervals, axes, empty state and anomaly markers: OK");

(async () => {
  const controls = Object.fromEntries(
    [...Object.keys(elements), "apply", "reset", "download-pdf", "error", "updated"]
      .map((id) => [id, new Element()])
  );
  for (const control of Object.values(controls)) {
    control.listeners = {};
    control.addEventListener = (event, handler) => {
      (control.listeners[event] ||= []).push(handler);
    };
  }
  const downloads = [];
  const resizeHandlers = [];
  const authenticatedContext = vm.createContext({
    document: { ...document, getElementById: (id) => controls[id] },
    Chart: ChartMock, Date, Number, Set, URLSearchParams,
    requestAnimationFrame: (callback) => callback(),
    window: {
      location: { assign: (url) => downloads.push(url) },
      addEventListener: (event, handler) => {
        if (event === "resize") resizeHandlers.push(handler);
      },
    },
    setInterval: () => {},
    fetch: async (url) => ({
      ok: true,
      json: async () => ({ results: url === "/api/sensors/" ? ["test-sensor"] : [] }),
    }),
  });
  vm.runInContext(
    source.replace(/refresh\(\);\r?\nsetInterval/, "globalThis.initialRefresh = refresh();\nsetInterval") +
      "\nglobalThis.refreshDashboard = refresh; globalThis.renderChart = renderChart;",
    authenticatedContext
  );
  await authenticatedContext.initialRefresh;
  for (let i = 0; i < 3; i++) await authenticatedContext.refreshDashboard();
  assert.equal(resizeHandlers.length, 1);
  resizeHandlers[0]();
  authenticatedContext.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: rows });
  const resizedChart = vm.runInContext("chart", authenticatedContext);
  resizeHandlers[0]();
  resizeHandlers[0]();
  assert.equal(resizedChart.resizeCount, 2);
  authenticatedContext.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: [] });
  resizeHandlers[0]();
  assert.equal(resizedChart.resizeCount, 2);
  assert.equal(controls.sensor.listeners.change.length, 1);
  assert.equal(controls.apply.listeners.click.length, 1);
  assert.equal(controls["download-pdf"].listeners.click.length, 1);
  for (const handler of controls["download-pdf"].listeners.click) handler();
  assert.equal(downloads.length, 1);
  assert.equal(new URL(downloads[0], "http://localhost").searchParams.get("sensor_id"), "test-sensor");
  authenticatedContext.renderChart({ metric: "turbidity", unit: "NTU", threshold: 30, results: rows });
  authenticatedContext.fetch = async () => ({ ok: false, status: 403 });
  await authenticatedContext.refreshDashboard();
  assert.equal(controls.chart.hidden, true);
  assert.match(controls["history-message"].textContent, /Logga in igen/);
  console.log("Dashboard event handlers remain single after repeated refreshes: OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

(async () => {
  const overviewControls = Object.fromEntries(["cards", "updated", "error", "summary-total", "summary-anomaly", "summary-stale"].map((id) => [id, new Element()]));
  const requests = [];
  const overview = vm.createContext({
    document: { ...document, getElementById: (id) => overviewControls[id] },
    Date, Number, Set, URLSearchParams,
    setInterval: () => {},
    fetch: async (url) => {
      requests.push(url);
      return { ok: true, json: async () => ({ results: [
        { ...reading, sensor_id: "oak-temperature", status: "ANOMALY", timestamp: new Date(now).toISOString() },
        { ...reading, sensor_id: "old-turbidity", timestamp: new Date(now - 301000).toISOString() },
      ] }) };
    },
  });
  vm.runInContext(source.replace(/refresh\(\);\r?\nsetInterval/, "globalThis.initialRefresh = refresh();\nsetInterval"), overview);
  await overview.initialRefresh;
  assert.deepEqual(requests, ["/api/readings/latest/"]);
  assert.equal(overviewControls["summary-total"].textContent, "2");
  assert.equal(overviewControls["summary-anomaly"].textContent, "1");
  assert.equal(overviewControls["summary-stale"].textContent, "1");
  console.log("Authenticated overview uses latest-only data and accurate summaries: OK");
})().catch((error) => { console.error(error); process.exitCode = 1; });

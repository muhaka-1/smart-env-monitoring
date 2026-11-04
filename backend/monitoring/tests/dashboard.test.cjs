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
}
class ChartMock {
  constructor(canvas, config) { this.data = config.data; this.options = config.options; }
  update() {}
  destroy() {}
}
const elements = {
  cards: new Element(), chart: new Element(), "history-message": new Element(),
  "chart-explanation": new Element(), "interval-summary": new Element(),
  from: new Element(), to: new Element(),
};
const main = new Element();
main.dataset.readingStaleSeconds = "300";
main.dataset.canViewHistory = "true";
const document = {
  querySelector: () => main,
  querySelectorAll: () => [],
  getElementById: (id) => elements[id],
  createElement: () => new Element(),
};
const source = fs.readFileSync(path.join(__dirname, "../static/monitoring/dashboard.js"), "utf8");
const initIndex = source.lastIndexOf("if (CAN_VIEW_HISTORY) {");
assert.notEqual(initIndex, -1);
const context = vm.createContext({ document, Chart: ChartMock, Date, Number, Set, URLSearchParams });
vm.runInContext(source.slice(0, initIndex) + "\nglobalThis.dashboard = { renderCards, renderChart, validateRange };", context);

const now = Date.now();
const reading = { metric: "turbidity", unit: "NTU", value: 2, status: "OK", threshold: 30 };
context.dashboard.renderCards([
  { ...reading, sensor_id: "fresh", timestamp: new Date(now - 1000).toISOString() },
  { ...reading, sensor_id: "old", timestamp: new Date(now - 301000).toISOString() },
]);
const text = (element) => typeof element === "string" ? element : element.textContent + element.children.map(text).join("");
assert.doesNotMatch(text(elements.cards.children[0]), /inaktuell/);
assert.match(text(elements.cards.children[1]), /inaktuell/);

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

assert.equal(context.dashboard.validateRange("", "").valid, true);
assert.equal(context.dashboard.validateRange("2026-01-01T10:00", "").valid, false);
assert.match(context.dashboard.validateRange("2026-01-01T11:00", "2026-01-01T10:00").message, /tidigare/);
assert.equal(context.dashboard.validateRange("2026-01-01T10:00", "2026-01-01T11:00").valid, true);

const publicElements = {
  cards: new Element(), error: new Element(), updated: new Element(),
};
const publicMain = new Element();
publicMain.dataset.readingStaleSeconds = "300";
publicMain.dataset.canViewHistory = "false";
const publicCalls = [];
const publicDocument = {
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
  console.log("Dashboard status, intervals, access control and anomaly markers: OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

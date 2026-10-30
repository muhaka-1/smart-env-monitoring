const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Chart = require("../static/monitoring/vendor/chart.umd.min.js");

class Element {
  constructor() { this.children = []; this.dataset = {}; this.hidden = false; this.textContent = ""; }
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
const elements = { cards: new Element(), chart: new Element(), "history-message": new Element() };
const main = new Element();
main.dataset.readingStaleSeconds = "300";
const document = {
  querySelector: () => main,
  getElementById: (id) => elements[id],
  createElement: () => new Element(),
};
const source = fs.readFileSync(path.join(__dirname, "../static/monitoring/dashboard.js"), "utf8");
const initIndex = source.indexOf('$("sensor").addEventListener');
assert.notEqual(initIndex, -1);
const context = vm.createContext({ document, Chart: ChartMock, Date, Number, Set });
vm.runInContext(source.slice(0, initIndex) + "\nglobalThis.dashboard = { renderCards, renderChart };", context);

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
const times = chart.data.datasets[0].data.map((point) => point.x);
assert.equal(times[2] - times[1], 3 * (times[1] - times[0]));
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
console.log("Dashboard staleness, time axis, tooltip timestamps and mixed metrics: OK");

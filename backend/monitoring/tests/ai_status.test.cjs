const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

module.exports = async function verifyStatusPanel() {
  class Element {
    constructor() { this.children = []; this.dataset = {}; this.textContent = ""; }
    replaceChildren(...items) { this.children = items; }
  }
  const elements = Object.fromEntries(["ai-status", "ai-status-text", "ai-status-badge", "ai-status-meta"].map((id) => [id, new Element()]));
  elements["ai-status"].dataset = {
    summaryUrl: "/api/ai/summary/", labelAi: "AI-genererad", labelAuto: "Automatisk sammanfattning",
    labelGenerated: "Skapad", labelAiNote: "Kontrollera värdena", labelError: "Kunde inte hämtas",
  };
  let result = { text: "6 mätpunkter\n\nOhio Street Beach: <script>untrusted</script>\n\nRainbow Beach: OK", source: "ai", model: "local-model", generated_at: new Date().toISOString() };
  let fail = false;
  const requests = [];
  const context = vm.createContext({
    document: { documentElement: { lang: "sv" }, getElementById: (id) => elements[id], createElement: () => new Element() },
    Date,
    setInterval: (callback, delay) => { assert.equal(delay, 60000); },
    fetch: async (url) => { requests.push(url); return { ok: !fail, status: 503, json: async () => result }; },
  });
  const source = fs.readFileSync(path.join(__dirname, "../static/monitoring/ai_status.js"), "utf8");
  vm.runInContext(source.replace("  refresh();", "  globalThis.runRefresh = refresh; globalThis.initialRefresh = refresh();"), context);
  await context.initialRefresh;
  assert.deepEqual(requests, ["/api/ai/summary/"]);
  assert.equal(elements["ai-status-text"].children.length, 3);
  assert.equal(elements["ai-status-text"].children[1].textContent, "Ohio Street Beach: <script>untrusted</script>");
  assert.equal(elements["ai-status-badge"].textContent, "AI-genererad");
  result = { ...result, text: "Ohio Street Beach: vanlig text", source: "fallback", model: null };
  await context.runRefresh();
  assert.equal(elements["ai-status-text"].children.length, 1);
  assert.equal(elements["ai-status-badge"].textContent, "Automatisk sammanfattning");
  assert.ok(!elements["ai-status-meta"].textContent.includes("local-model"));
  fail = true;
  await context.runRefresh();
  assert.equal(elements["ai-status-text"].textContent, "Kunde inte hämtas");
  assert.equal(elements["ai-status-badge"].textContent, "—");
  process.stdout.write("Beach summary paragraphs, labels, refresh, failure and safe text rendering: OK\n");
};

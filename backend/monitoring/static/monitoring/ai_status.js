// "Läget just nu": hämtar sammanfattning och datakvalitet. Texten sätts med textContent (aldrig HTML).
(() => {
  const panel = document.getElementById("ai-status");
  if (!panel) return;
  const label = (name) => panel.dataset[name] || "";
  const $ = (id) => document.getElementById(id);
  const REFRESH_MS = 60000;
  const locale = document.documentElement.lang || "sv";

  async function getJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  }

  function renderSummary(data) {
    const paragraphs = data.text.split(/\n\n+/).filter(Boolean).map((text) => {
      const paragraph = document.createElement("p");
      paragraph.className = "mb-2";
      paragraph.textContent = text;
      return paragraph;
    });
    $("ai-status-text").replaceChildren(...paragraphs);
    const badge = $("ai-status-badge");
    const isAi = data.source === "ai";
    badge.textContent = isAi ? label("labelAi") : label("labelAuto");
    badge.className = "badge " + (isAi ? "bg-info text-dark" : "bg-secondary");
    const time = new Date(data.generated_at);
    const parts = [];
    if (!Number.isNaN(time.getTime())) {
      parts.push(`${label("labelGenerated")} ${time.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })}`);
    }
    if (isAi && data.model) parts.push(data.model);
    if (isAi) parts.push(label("labelAiNote"));
    $("ai-status-meta").textContent = parts.join(" · ");
  }

  function renderQuality(data) {
    const list = $("ai-quality-list");
    list.replaceChildren();
    const items = data.results || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.textContent = label("labelNoFlags");
      list.append(li);
      return;
    }
    for (const item of items.slice(0, 5)) {
      const li = document.createElement("li");
      const when = new Date(item.timestamp).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });
      li.textContent = `${item.sensor_id} · ${item.metric_label} ${item.value} ${item.unit} · ${item.kind_label}: ${item.reason_label} (${when})`;
      list.append(li);
    }
  }

  async function refresh() {
    try {
      renderSummary(await getJSON(panel.dataset.summaryUrl));
    } catch (error) {
      $("ai-status-text").textContent = label("labelError");
      $("ai-status-badge").textContent = "—";
    }
    if (!panel.dataset.assessmentsUrl) return;
    try {
      renderQuality(await getJSON(panel.dataset.assessmentsUrl + "?limit=5"));
    } catch (error) {
      $("ai-quality-list").replaceChildren();
    }
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();

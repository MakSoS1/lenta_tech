const input = document.querySelector("#video-file");
const label = document.querySelector("#file-label");
const statusText = document.querySelector("#demo-status");
const count = document.querySelector("#demo-count");
const progress = document.querySelector("#progress-bar");

input?.addEventListener("change", () => {
  const file = input.files?.[0];
  if (!file) return;

  label.textContent = file.name;
  statusText.textContent = "Файл выбран. Локальный API обработает его командой run_api.py";
  count.textContent = file.size > 0 ? "CSV ready" : "sample CSV";
  progress.style.width = "100%";
});

const statusColors = {
  done: "#16764a",
  partial: "#f4b740",
  failed: "#d92832",
  planned: "#245f9f",
  researched: "#245f9f",
};

const repoBlobBase = "https://github.com/MakSoS1/lenta_tech/blob/main/";

function setSelectedNote(note) {
  const title = document.querySelector("#kg-note-title");
  const summary = document.querySelector("#kg-note-summary");
  const link = document.querySelector("#kg-note-link");
  if (!note || !title || !summary || !link) return;
  title.textContent = note.title;
  summary.textContent = note.summary;
  link.href = repoBlobBase + note.path;
}

function graphPosition(note, index, groupIndex, groupCount) {
  const lane = {
    plan: 135,
    summary: 135,
    component: 470,
    attempt: 840,
  }[note.group] || 620;
  const y = 70 + (index + 0.5) * (580 / Math.max(groupCount, 1));
  return { x: lane, y };
}

function renderKnowledgeGraph(data) {
  const svg = document.querySelector("#knowledge-graph");
  const list = document.querySelector("#knowledge-list");
  if (!svg || !list || !data?.nodes?.length) return;

  document.querySelector("#kg-note-count").textContent = String(data.nodes.length);
  document.querySelector("#kg-edge-count").textContent = String(data.edges.length);

  const byId = new Map(data.nodes.map((node) => [node.id, node]));
  const groups = data.nodes.reduce((acc, node) => {
    const key = node.group || "summary";
    acc[key] = acc[key] || [];
    acc[key].push(node);
    return acc;
  }, {});
  Object.values(groups).forEach((items) => items.sort((a, b) => a.title.localeCompare(b.title, "ru")));

  const positions = new Map();
  for (const [group, items] of Object.entries(groups)) {
    items.forEach((node, index) => positions.set(node.id, graphPosition(node, index, group, items.length)));
  }

  svg.innerHTML = "";
  for (const edge of data.edges) {
    const a = positions.get(edge.source);
    const b = positions.get(edge.target);
    if (!a || !b) continue;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "kg-edge");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    svg.appendChild(line);
  }

  for (const node of data.nodes) {
    const pos = positions.get(node.id);
    if (!pos) continue;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "kg-node");
    circle.setAttribute("cx", pos.x);
    circle.setAttribute("cy", pos.y);
    circle.setAttribute("r", node.group === "attempt" ? "10" : "14");
    circle.setAttribute("fill", statusColors[node.status] || statusColors.researched);
    circle.setAttribute("tabindex", "0");
    circle.setAttribute("role", "button");
    circle.setAttribute("aria-label", node.title);
    circle.addEventListener("click", () => setSelectedNote(node));
    circle.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") setSelectedNote(node);
    });
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${node.title} — ${node.status}`;
    circle.appendChild(title);
    svg.appendChild(circle);
  }

  ["plan", "component", "attempt"].forEach((group) => {
    const x = { plan: 80, component: 400, attempt: 760 }[group];
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("class", "kg-label");
    label.setAttribute("x", x);
    label.setAttribute("y", "36");
    label.textContent = group === "plan" ? "strategy" : group;
    svg.appendChild(label);
  });

  list.innerHTML = "";
  data.nodes.forEach((node) => {
    const item = document.createElement("button");
    item.type = "button";
    item.innerHTML = `<small>${node.group} · ${node.status}</small><strong></strong><p></p>`;
    item.querySelector("strong").textContent = node.title;
    item.querySelector("p").textContent = node.summary;
    item.addEventListener("click", () => setSelectedNote(node));
    list.appendChild(item);
  });

  setSelectedNote(byId.get("lenta-tech-life-hack-knowledge-graph") || data.nodes[0]);
}

if (document.querySelector("#knowledge-graph")) {
  fetch("./assets/knowledge-graph.json")
    .then((response) => response.json())
    .then(renderKnowledgeGraph)
    .catch(() => {
      const summary = document.querySelector("#kg-note-summary");
      if (summary) summary.textContent = "Не удалось загрузить graph.json. Проверьте site/assets/knowledge-graph.json.";
    });
}

const knowledgeGraphSource = "./assets/knowledge-graph.json";
const repoBlobBase = "https://github.com/MakSoS1/lenta_tech/blob/main/";

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 МБ";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} МБ`;
}

function bindDemoUpload() {
  const input = document.querySelector("#video-file");
  const label = document.querySelector("#file-label");
  const name = document.querySelector("#selected-file-name");
  const size = document.querySelector("#selected-file-size");

  if (!input) return;
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (!file) return;
    if (label) label.textContent = file.name;
    if (name) name.textContent = file.name;
    if (size) size.textContent = formatBytes(file.size);
  });
}

function bindCopyButtons() {
  const buttons = document.querySelectorAll("[data-copy-target]");
  if (!buttons.length) return;

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const targetSelector = button.getAttribute("data-copy-target");
      if (!targetSelector) return;
      const target = document.querySelector(targetSelector);
      if (!target) return;
      const text = target.textContent?.trim();
      if (!text) return;

      try {
        await navigator.clipboard.writeText(text);
        const original = button.textContent;
        button.textContent = "Скопировано";
        window.setTimeout(() => {
          if (original) button.textContent = original;
        }, 1000);
      } catch (_error) {
        button.textContent = "Ошибка";
      }
    });
  });
}

function bindHypothesisNodes() {
  const nodes = document.querySelectorAll(".hyp-node");
  if (!nodes.length) return;

  const title = document.querySelector("#kg-note-title");
  const summary = document.querySelector("#kg-note-summary");
  const badge = document.querySelector("#kg-note-badge");
  const link = document.querySelector("#kg-note-link");

  function updatePanel(node) {
    if (!title || !summary || !badge || !link) return;
    const nodeTitle = node.getAttribute("data-title") || "Гипотеза";
    const nodeSummary = node.getAttribute("data-summary") || "Описание отсутствует.";
    const nodeStatus = node.getAttribute("data-note") || "Принято";

    title.textContent = nodeTitle;
    summary.textContent = nodeSummary;
    badge.textContent = nodeStatus;
    badge.className = "badge";
    const statusValue = node.getAttribute("data-status");
    if (statusValue === "accepted") badge.classList.add("accepted");
    if (statusValue === "partial") badge.classList.add("partial");
    if (statusValue === "rejected") badge.classList.add("rejected");
    link.href = `${repoBlobBase}docs/knowledge/README.md`;

    nodes.forEach((item) => item.classList.remove("active"));
    node.classList.add("active");
  }

  nodes.forEach((node) => {
    node.addEventListener("click", () => updatePanel(node));
  });
}

function preloadKnowledgeStats() {
  const graphMount = document.querySelector("#knowledge-graph");
  const listMount = document.querySelector("#knowledge-list");
  if (!graphMount || !listMount) return;

  fetch(knowledgeGraphSource)
    .then((response) => response.json())
    .then((payload) => {
      const notes = Array.isArray(payload?.nodes) ? payload.nodes.length : 0;
      const links = Array.isArray(payload?.edges) ? payload.edges.length : 0;
      graphMount.dataset.noteCount = String(notes);
      listMount.dataset.edgeCount = String(links);
    })
    .catch(() => {
      graphMount.dataset.noteCount = "0";
      listMount.dataset.edgeCount = "0";
    });
}

bindDemoUpload();
bindCopyButtons();
bindHypothesisNodes();
preloadKnowledgeStats();

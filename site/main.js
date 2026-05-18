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

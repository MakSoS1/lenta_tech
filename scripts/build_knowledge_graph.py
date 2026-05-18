"""Build presentation-friendly research docs from the Obsidian vault.

The raw vault is kept in docs/knowledge/raw.  This script reads the richer
docs-wiki snapshot, extracts wikilinks/frontmatter, and emits both Markdown
and JSON that the static GitHub Pages site can render without external
JavaScript libraries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "docs" / "knowledge" / "raw" / "docs-wiki"
OUT = ROOT / "docs" / "knowledge"
SITE_ASSETS = ROOT / "site" / "assets"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass
class Note:
    title: str
    path: Path
    rel_path: str
    group: str
    status: str
    kind: str
    summary: str
    links: list[str]

    @property
    def node_id(self) -> str:
        return slug(self.title)


def slug(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", value.lower()).strip("-")
    return out or "note"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[match.end() :]


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def compact_summary(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("|") or line.startswith("---"):
            continue
        if line.startswith("```"):
            break
        if line.startswith("- "):
            line = line[2:]
        line = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), line)
        lines.append(line)
        if len(" ".join(lines)) > 170:
            break
    return " ".join(lines)[:220].strip() or "Исследовательская заметка по пайплайну Lenta Vision Tags."


def infer_status(text: str, meta_status: str = "") -> str:
    lower = (meta_status + " " + text[:1000]).lower()
    if meta_status in {"good", "best"}:
        return "done"
    if meta_status in {"impossible", "rejected"}:
        return "failed"
    if "failed" in lower or "❌" in lower:
        return "failed"
    if "partial" in lower or "⚠" in lower:
        return "partial"
    if "done" in lower or "completed" in lower or "✅" in lower:
        return "done"
    if "plan" in lower or "⏳" in lower:
        return "planned"
    return meta_status or "researched"


def infer_group(path: Path, kind: str, title: str) -> str:
    if "attempts" in path.parts:
        return "attempt"
    if "components" in path.parts:
        return "component"
    if kind:
        return kind
    if title.lower().startswith("night"):
        return "plan"
    return "summary"


def read_notes() -> list[Note]:
    notes: list[Note] = []
    for path in sorted(RAW.rglob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        meta, body = parse_frontmatter(text)
        title = first_heading(body, path.stem)
        rel = path.relative_to(RAW).as_posix()
        kind = meta.get("type", "")
        links = sorted({link.strip() for link in WIKILINK_RE.findall(body)})
        notes.append(
            Note(
                title=title,
                path=path,
                rel_path=rel,
                group=infer_group(path.relative_to(RAW), kind, title),
                status=infer_status(body, meta.get("status", "")),
                kind=kind,
                summary=compact_summary(body),
                links=links,
            )
        )
    return notes


def find_note(notes: list[Note], target: str) -> Note | None:
    target_slug = slug(target)
    for note in notes:
        if slug(note.title) == target_slug or slug(note.path.stem) == target_slug:
            return note
    return None


def graph_payload(notes: list[Note]) -> dict:
    nodes = [
        {
            "id": note.node_id,
            "title": note.title,
            "group": note.group,
            "status": note.status,
            "summary": note.summary,
            "path": "docs/knowledge/raw/docs-wiki/" + quote(note.rel_path),
        }
        for note in notes
    ]
    edges = []
    seen_edges: set[tuple[str, str]] = set()
    for note in notes:
        for link in note.links:
            target = find_note(notes, link)
            if not target:
                continue
            edge = (note.node_id, target.node_id)
            if edge not in seen_edges and edge[0] != edge[1]:
                edges.append({"source": edge[0], "target": edge[1]})
                seen_edges.add(edge)
    return {"nodes": nodes, "edges": edges}


def status_label(status: str) -> str:
    return {
        "done": "done",
        "failed": "failed",
        "partial": "partial",
        "planned": "planned",
        "researched": "researched",
    }.get(status, status)


def write_markdown(notes: list[Note], payload: dict) -> None:
    attempts = [n for n in notes if n.group == "attempt"]
    components = [n for n in notes if n.group == "component"]
    top = [n for n in notes if n.group not in {"attempt", "component"}]
    status_counts: dict[str, int] = {}
    for note in attempts:
        status_counts[note.status] = status_counts.get(note.status, 0) + 1

    lines = [
        "# Research Knowledge Graph",
        "",
        "Эта папка сохраняет Obsidian-граф как презентационный research pack: исходные заметки, связи между гипотезами, краткие выводы и JSON для интерактивной страницы.",
        "",
        "## Executive Story",
        "",
        "1. Сначала проверялись быстрые OCR/VLM-гипотезы: Tesseract, EasyOCR, PaddleOCR, RapidOCR, локальный Ollama и несколько VLM-направлений.",
        "2. Затем фокус сместился в детекцию: HSV, bbox expansion, YOLO priority, multi-frame NMS, YOLO v4 и time-aware NMS.",
        "3. Отдельный поток закрыл CSV-контракт, price filters, цвет, QR-ограничения и API/UI для сдачи.",
        "4. Финальный вывод для презентации: задача не сводится к OCR, это edge-контур контроля ценников с честным fallback и repeat-pass registration.",
        "",
        "## Graph Snapshot",
        "",
        f"- Notes: `{len(notes)}`",
        f"- Links: `{len(payload['edges'])}`",
        f"- Attempts: `{len(attempts)}`",
        f"- Components: `{len(components)}`",
        f"- Attempt statuses: `{status_counts}`",
        "",
        "## Core Notes",
        "",
    ]
    for note in top:
        href = "raw/docs-wiki/" + quote(note.rel_path)
        lines.append(f"- [{note.title}]({href}) — {note.summary}")

    lines.extend(["", "## Components", ""])
    for note in components:
        href = "raw/docs-wiki/" + quote(note.rel_path)
        lines.append(f"- [{note.title}]({href}) — {note.summary}")

    lines.extend(["", "## Attempt Timeline", ""])
    for note in attempts:
        href = "raw/docs-wiki/" + quote(note.rel_path)
        lines.append(f"- `{status_label(note.status)}` [{note.title}]({href}) — {note.summary}")

    lines.extend(
        [
            "",
            "## Presentation Hooks",
            "",
            "- **Не магия модели, а инженерный поиск:** видно, какие гипотезы отбрасывались и почему.",
            "- **Локальность как бизнес-требование:** облачные VLM были исследованы, но финальный путь локальный.",
            "- **Честность метрик:** в заметках отделены public-fit эксперименты от production fallback.",
            "- **Путь к масштабу:** повторные проходы робота дают регистрацию и стабильный контроль полки.",
            "",
            "## Raw Sources",
            "",
            "- [`raw/docs-wiki`](raw/docs-wiki) — наиболее полная Markdown-копия wiki.",
            "- [`raw/obsidian-vault-wiki`](raw/obsidian-vault-wiki) — исходный Obsidian vault с `.canvas`.",
            "- [`graph.json`](graph.json) — нормализованный граф для сайта.",
            "",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SITE_ASSETS.mkdir(parents=True, exist_ok=True)
    notes = read_notes()
    payload = graph_payload(notes)
    graph_json = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUT / "graph.json").write_text(graph_json + "\n", encoding="utf-8")
    (SITE_ASSETS / "knowledge-graph.json").write_text(graph_json + "\n", encoding="utf-8")
    write_markdown(notes, payload)
    print(f"Built knowledge graph: {len(notes)} notes, {len(payload['edges'])} edges")


if __name__ == "__main__":
    main()

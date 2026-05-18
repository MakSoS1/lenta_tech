import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "src"):
            if key in attrs:
                self.refs.append(attrs[key])


def local_path(ref: str) -> Path | None:
    parsed = urlparse(ref)
    if parsed.scheme or ref.startswith("#"):
        return None
    clean = ref.split("#", 1)[0].split("?", 1)[0]
    if not clean:
        return None
    return (SITE / clean).resolve()


class StaticSiteTest(unittest.TestCase):
    PAGES = [
        "index.html",
        "demo.html",
        "architecture.html",
        "metrics.html",
        "docs.html",
        "roadmap.html",
        "results.html",
        "knowledge.html",
    ]

    def test_html_references_exist(self):
        for page in self.PAGES:
            parser = AssetParser()
            parser.feed((SITE / page).read_text(encoding="utf-8"))
            for ref in parser.refs:
                path = local_path(ref)
                if path is None:
                    continue
                self.assertTrue(path.exists(), f"{page} references missing asset {ref}")

    def test_site_has_no_cdn_runtime_dependency(self):
        html_pages = [(SITE / page).read_text(encoding="utf-8") for page in self.PAGES]
        text = "\n".join(
            html_pages
            + [
                (SITE / "main.js").read_text(encoding="utf-8"),
                (SITE / "styles.css").read_text(encoding="utf-8"),
            ]
        )
        forbidden = re.findall(r"https://(cdn|unpkg|esm|jsdelivr)\.", text)
        self.assertEqual(forbidden, [])

    def test_knowledge_page_has_graph_mounts(self):
        html = (SITE / "knowledge.html").read_text(encoding="utf-8")
        self.assertIn('id="knowledge-graph"', html)
        self.assertIn('id="knowledge-list"', html)
        self.assertIn("./assets/knowledge-graph.json", (SITE / "main.js").read_text(encoding="utf-8"))

    def test_brand_logo_exists(self):
        self.assertTrue((SITE / "assets" / "lenta-vision-mark.svg").exists())

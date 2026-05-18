import json
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeGraphTest(unittest.TestCase):
    def test_graph_json_is_connected_to_raw_notes(self):
        graph_path = ROOT / "docs" / "knowledge" / "graph.json"
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        node_ids = {node["id"] for node in data["nodes"]}

        self.assertGreaterEqual(len(data["nodes"]), 39)
        self.assertGreaterEqual(len(data["edges"]), 60)
        self.assertIn("lenta-tech-life-hack-knowledge-graph", node_ids)
        self.assertIn("qr-decoding", node_ids)
        self.assertIn("a24-time-aware-nms", node_ids)

        for node in data["nodes"]:
            raw_path = ROOT / unquote(node["path"])
            self.assertTrue(raw_path.exists(), node["path"])
            self.assertIn(node["status"], {"done", "failed", "partial", "planned", "researched"})

        for edge in data["edges"]:
            self.assertIn(edge["source"], node_ids)
            self.assertIn(edge["target"], node_ids)

    def test_site_uses_same_graph_payload(self):
        docs_graph = json.loads((ROOT / "docs" / "knowledge" / "graph.json").read_text(encoding="utf-8"))
        site_graph = json.loads((ROOT / "site" / "assets" / "knowledge-graph.json").read_text(encoding="utf-8"))
        self.assertEqual(docs_graph, site_graph)

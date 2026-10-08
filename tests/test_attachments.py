import copy
import json
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from matching import MatchingEngine
from matching.attachments import AttachmentSystem
from matching.render import render_svg
from matching.server import create_server
from matching.topology import (TopologyError, load_topology_catalog,
                               topology_catalog_id, validate_topology_catalog)

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGIES = ROOT / "data/topologies.json"
SVG_NS = "{http://www.w3.org/2000/svg}"


@unittest.skipUnless(TOPOLOGIES.is_file(), "Run python -m matching build first")
class AttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MatchingEngine.from_file()
        cls.registry = load_topology_catalog(TOPOLOGIES)

    def test_all_5280_diagrams_attach_to_complete_valid_graphs(self):
        self.assertEqual(self.engine.validate_attachments(), {
            "topology_count": 7, "template_count": 28, "validated_model_diagram_count": 5280})
        for diagram in self.engine._catalog["diagrams"]:
            packet = self.engine.attachment(diagram["id"])
            lines = packet["attachment"]["lines"]
            original = {line["slot"]: line for line in
                        diagram["external_lines"] + diagram["internal_lines"]}
            fermions = Counter()
            with self.subTest(diagram_id=diagram["id"]):
                self.assertEqual(len(lines), len(original))
                self.assertEqual(set(packet["slot_to_edge"]), set(original))
                self.assertEqual(len(packet["edge_to_slot"]), len(original))
                for line in lines:
                    for key, value in original[line["slot"]].items():
                        self.assertEqual(line["field"][key], value)
                    if line["statistics"] == "F":
                        fermions[line["source"]] += 1
                        fermions[line["target"]] += 1
                self.assertTrue(all(fermions[vertex["id"]] in (0, 2)
                                    for vertex in packet["attachment"]["vertices"]
                                    if vertex["kind"] == "interaction"))

    def test_t1_1_1_exact_geometry_field_assignment_and_lm_edges(self):
        packet = self.engine.attachment("T1-1-1")
        self.assertEqual(packet["pipeline"], [
            {"stage": "topology", "id": "T1"},
            {"stage": "diagram", "id": "T1-1"},
            {"stage": "attachment", "id": "T1-1-1"}])
        expected = {"I1": ("o", "c1", "24^*"), "I2": ("o", "c2", "13"),
                    "I3": ("o", "c3", "52^*"), "I4": ("c3", "c4", "56")}
        for line in packet["attachment"]["lines"]:
            if line["slot"] in expected:
                self.assertEqual((line["source"], line["target"], line["field"]["display_label"]),
                                 expected[line["slot"]])
            number = int(line["slot"][1:]) * (-1 if line["slot"].startswith("E") else 1)
            self.assertEqual(line["lm_edge_number"], number)
        vertices = {v["id"]: v for v in packet["attachment"]["vertices"]}
        self.assertEqual(vertices["o"]["lm_vertex_id"], 1)
        self.assertEqual(vertices["c1"]["lm_vertex_id"], 8)
        self.assertEqual(packet["attachment"]["vertex_attachments"]["o"],
                         {"external_slots": ["E4"], "internal_slots": ["I1", "I2", "I3"]})

    def test_effective_conjugate_quantum_numbers_and_sm_attachments(self):
        lines = {line["slot"]: line for line in
                 self.engine.attachment("T1-1-1")["attachment"]["lines"]}
        self.assertEqual(lines["I1"]["field"]["canonical_quantum"]["su3"]["dynkin"], [1, 0])
        self.assertEqual(lines["I1"]["field"]["attached_quantum"]["su3"]["dynkin"], [0, 1])
        self.assertEqual(lines["I1"]["field"]["attached_quantum"]["hypercharge"]["text"], "-7/6")
        self.assertEqual(lines["I3"]["field"]["attached_quantum"]["hypercharge"]["text"], "1")
        self.assertEqual(lines["E1"]["field"]["sm_symbol"], "Q_L")
        self.assertEqual(lines["E4"]["field"]["attached_quantum"]["hypercharge"]["text"], "-1/2")

    def test_t5_6_slot_correction_and_t6_2_distinct_layout_are_preserved(self):
        lines = {line["slot"]: line for line in
                 self.engine.attachment("T5-6-1")["attachment"]["lines"]}
        self.assertEqual((lines["I4"]["source"], lines["I4"]["target"]), ("c4", "c5"))
        self.assertEqual((lines["I5"]["source"], lines["I5"]["target"]), ("c3", "c4"))
        self.assertEqual(lines["I4"]["statistics"], "S")
        self.assertEqual(lines["I5"]["statistics"], "F")
        t61 = {v["id"]: v for v in self.engine.diagram_template("T6-1")["vertices"]}
        t62 = {v["id"]: v for v in self.engine.diagram_template("T6-2")["vertices"]}
        self.assertGreater(t61["c4"]["y"], 0)
        self.assertLess(t62["c4"]["y"], 0)
        self.assertEqual(len(self.registry["normalization_corrections"]), 5)

    def test_repeated_field_lines_remain_separate_and_can_highlight_together(self):
        packet = self.engine.attachment("T1-1-3")
        self.assertEqual(packet["field_to_lines"]["56"], ["I1", "I4"])
        self.assertEqual(len(packet["field_to_edges"]["56"]), 2)
        svg = ET.fromstring(render_svg(packet))
        self.assertEqual(len([node for node in svg.iter(SVG_NS + "g")
                              if node.get("data-field-id") == "56"]), 2)

    def test_three_svg_stages_have_stable_hit_targets_and_correct_labels(self):
        packet = self.engine.attachment("T1-1-1")
        for stage in ("topology", "diagram", "attachment"):
            root = ET.fromstring(render_svg(packet, stage))
            groups = [node for node in root.iter(SVG_NS + "g") if node.get("data-line-slot")]
            self.assertEqual(len(groups), 12)
            texts = {node.get("id"): "".join(node.itertext()) for node in root.iter(SVG_NS + "text")}
            if stage == "topology":
                self.assertEqual(texts, {})
                self.assertEqual(list(root.iter(SVG_NS + "polygon")), [])
            elif stage == "diagram":
                self.assertEqual(texts["label-I1"], "I1")
            else:
                self.assertEqual(texts["label-I1"], "24*")
                self.assertEqual(texts["label-E1"], "QL*")
        with self.assertRaises(ValueError):
            render_svg(packet, "bad-stage")

    def test_bad_registry_binding_and_stale_model_snapshot_are_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["templates"][0]["lines"][0]["lm_edge_number"] = 999
        registry["topology_catalog_id"] = topology_catalog_id(registry)
        with self.assertRaises(TopologyError):
            validate_topology_catalog(registry)
        registry = copy.deepcopy(self.registry)
        registry["validated_model_catalog_id"] = "stale"
        with self.assertRaises(TopologyError):
            AttachmentSystem(self.engine._catalog, registry)

    def test_returned_attachment_cannot_mutate_later_queries(self):
        packet = self.engine.attachment("T1-1-1")
        packet["attachment"]["lines"][0]["field"]["display_label"] = "changed"
        packet["attachment"]["vertices"].clear()
        again = self.engine.attachment("T1-1-1")
        self.assertEqual(again["attachment"]["lines"][0]["field"]["display_label"], "Q_L^*")
        self.assertEqual(len(again["attachment"]["vertices"]), 13)
        with self.assertRaises(TopologyError):
            self.engine.attachment("T1-1-9999")

    def test_model_diagram_can_include_attachment_in_one_query(self):
        result = self.engine.model_diagram("T1-1-1", include_attachment=True)
        self.assertEqual(result["topology_attachment"]["model_diagram_id"], result["id"])


@unittest.skipUnless(TOPOLOGIES.is_file(), "Run python -m matching build first")
class AttachmentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(MatchingEngine.from_file(), port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_click_lookup_json_svg_search_and_unknown_id(self):
        with urlopen(self.base + "/api/attachments/T1-1-1") as response:
            packet = json.load(response)
        self.assertEqual(packet["model_diagram_id"], "T1-1-1")
        with urlopen(self.base + "/api/attachments/T1-1-1.svg?stage=attachment") as response:
            svg = ET.fromstring(response.read())
        self.assertEqual(svg.get("data-model-diagram-id"), "T1-1-1")
        with urlopen(self.base + "/api/diagrams?q=T1-1-1") as response:
            result = json.load(response)
        self.assertIn("T1-1-1", [item["id"] for item in result["items"]])
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + "/api/attachments/T1-1-9999")
        self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

"""Integration checks for the workbench's real-data HTTP endpoints."""
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from matching import MatchingEngine
from matching.server import create_server

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "data/topologies.json").is_file(), "Build data snapshots first")
class WorkbenchApiTests(unittest.TestCase):
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

    def get(self, route):
        with urlopen(self.base + route) as response:
            return json.load(response)

    def test_field_dictionary_preserves_all_ids_quantum_and_sm_markers(self):
        data = self.get("/api/fields")
        self.assertEqual(len(data["fields"]), 61)
        self.assertEqual([field["id"] for field in data["fields"]], list(range(1, 62)))
        self.assertEqual(data["statistics"]["diagram_count"], 5280)
        field = next(field for field in data["fields"] if field["id"] == 2)
        self.assertEqual(field["statistics"], "F")
        self.assertEqual(field["hypercharge"]["text"], "-1")
        self.assertEqual(field["sm_quantum_matches"][0]["symbol"], "e_R")

    def test_complete_selection_and_round_id_drive_candidate_colors(self):
        pending = self.get("/api/match?fields=52,1,52&request_id=round-7")
        self.assertEqual(pending["selected_field_ids"], [1, 52])
        self.assertEqual(pending["request_id"], "round-7")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["min_additional_fields"], 1)
        self.assertEqual(pending["next_fields"]["56"]["color"], "red")
        self.assertEqual(pending["next_fields"]["5"]["color"], "green")
        self.assertEqual(pending["next_fields"]["2"]["state"], "hidden")
        ready = self.get("/api/match?fields=1,52,56")
        self.assertEqual(ready["status"], "ready_minimal")
        self.assertEqual(ready["generation"]["model_field_ids"], ["MF-3i-23"])
        self.assertEqual(ready["generation"]["diagram_count"], 7)

    def test_exact_models_are_returned_only_after_complete_selection(self):
        self.assertEqual(self.get("/api/models")["items"], [])
        self.assertEqual(self.get("/api/models?fields=1,52")["items"], [])
        data = self.get("/api/models?fields=1,52,56")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["diagram_count"], 7)
        self.assertEqual(data["items"][0]["id"], "MF-3i-23")
        model = self.get("/api/models/MF-3i-23")
        self.assertEqual(model["diagram_ids"], data["items"][0]["diagram_ids"])

    def test_nonminimal_set_keeps_original_t_ids_without_fabricating_mf_number(self):
        data = self.get("/api/models?fields=13,30,40,48")
        self.assertEqual(data["count"], 1)
        model = data["items"][0]
        self.assertFalse(model["minimal"])
        self.assertIsNone(model["model_field_id"])
        self.assertEqual(model["diagram_ids"], ["T1-1-41", "T1-1-56"])
        self.assertEqual(self.get("/api/models/" + model["id"])["field_ids"], [13, 30, 40, 48])

    def test_bad_fields_or_model_ids_are_rejected(self):
        for route in ("/api/match?fields=99", "/api/match?fields=1.5",
                      "/api/match?fields=1,", "/api/models?fields=0",
                      "/api/models/MF-3i-99999"):
            with self.subTest(route=route), self.assertRaises(HTTPError) as raised:
                urlopen(self.base + route)
            self.assertEqual(raised.exception.code, 400)

    def test_static_asset_allowlist_and_legacy_viewer(self):
        expected = {"/": "text/html", "/attachment": "text/html",
                    "/assets/app.css": "text/css", "/assets/app.js": "text/javascript",
                    "/assets/i18n.js": "text/javascript", "/assets/attachment.js": "text/javascript",
                    "/assets/app-icon.svg": "image/svg+xml", "/favicon.ico": "image/x-icon"}
        for route, mime in expected.items():
            with self.subTest(route=route), urlopen(self.base + route) as response:
                self.assertTrue(response.headers["Content-Type"].startswith(mime))
                self.assertTrue(response.read())
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + "/assets/../config/sources.json")
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()

"""Integration checks against the generated 61-field / 5,280-diagram snapshot."""
import itertools
import random
import unittest
from pathlib import Path

from matching.engine import MatchingEngine

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


@unittest.skipUnless(CATALOG.is_file(), "Run python -m matching build first")
class RealCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MatchingEngine.from_file(CATALOG)
        cls.models = cls.engine._catalog["models"]
        cls.sets = [(model["id"], frozenset(model["field_ids"]), model["minimal"])
                    for model in cls.models]
        cls.minimal_sets = [fields for _, fields, minimal in cls.sets if minimal]

    def test_expected_data_counts_and_reference_validation(self):
        summary = self.engine.summary()
        self.assertEqual(summary["statistics"], {
            "field_count": 61, "model_count": 3021, "minimal_model_count": 710,
            "diagram_count": 5280, "minimal_diagram_count": 1450, "template_count": 28,
            "models_by_field_count": {"3": 134, "4": 812, "5": 2075},
        })
        self.assertEqual(summary["reference_validation"], {
            "audit_flag_rows": 5280, "published_model_diagram_rows": 5280,
            "published_minimal_model_rows": 710,
            "corrected_original_flags": 698,
        })

    def test_all_3021_complete_sets_and_minimal_classifications(self):
        for model in self.models:
            result = self.engine.match(model["field_ids"])
            expected_status = "ready_minimal" if model["minimal"] else "ready_model"
            with self.subTest(model_id=model["id"]):
                self.assertEqual(result["complete_model_ids"], [model["id"]])
                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["complete_diagram_count"], model["diagram_count"])

    def test_index_matches_independent_brute_force_for_sampled_selections(self):
        rng = random.Random(20261007)
        samples = {(), (1,), (1, 52, 56), (13, 30, 40, 48), (30, 40, 48)}
        for _ in range(300):
            model = rng.choice(self.models)
            samples.add(tuple(sorted(rng.sample(model["field_ids"],
                                               rng.randint(1, len(model["field_ids"]))))))
            samples.add(tuple(sorted(rng.sample(range(1, 62), rng.randint(1, 6)))))
        for selection in sorted(samples):
            selected = frozenset(selection)
            expected = [model_id for model_id, fields, _ in self.sets if selected <= fields]
            result = self.engine.match(selection)
            with self.subTest(selection=selection):
                self.assertEqual(result["compatible_model_ids"], expected)
                for field_id in range(1, 62):
                    if not selected or field_id in selected:
                        continue
                    extended = selected | {field_id}
                    has_any = any(extended <= fields for _, fields, _ in self.sets)
                    has_minimal = any(extended <= fields for fields in self.minimal_sets)
                    state = result["next_fields"][str(field_id)]
                    expected_color = "red" if has_minimal else ("green" if has_any else None)
                    self.assertEqual(state["color"], expected_color)
                if selected and expected:
                    expected_missing = min(len(fields - selected) for _, fields, _ in self.sets
                                           if selected <= fields)
                    self.assertEqual(result["min_additional_fields"], expected_missing)

    def test_all_field_pairs_match_shared_model_oracle(self):
        for left, right in itertools.combinations(range(1, 62), 2):
            expected = [model_id for model_id, fields, _ in self.sets
                        if left in fields and right in fields]
            result = self.engine.field_compatibility(left, right)
            with self.subTest(pair=(left, right)):
                self.assertEqual(result["compatible_model_ids"], expected)

    def test_known_minimality_regressions(self):
        smaller = self.engine.diagram("T1-1-42")
        larger = self.engine.diagram("T1-1-41")
        self.assertEqual(self.engine.model(smaller["model_id"])["field_ids"], [30, 40, 48])
        self.assertTrue(self.engine.model(smaller["model_id"])["minimal"])
        self.assertFalse(self.engine.model(larger["model_id"])["minimal"])
        repeated = self.engine.diagram("T4-1-3")
        self.assertEqual(self.engine.model(repeated["model_id"])["field_ids"], [1, 52, 56])
        self.assertTrue(self.engine.model(repeated["model_id"])["minimal"])

    def test_numbered_sm_matching_field_remains_bsm(self):
        field = self.engine.field(7)
        self.assertIn({"symbol": "H", "conjugated": True}, field["sm_quantum_matches"])
        diagram = self.engine.diagram("T1-1-5")
        self.assertEqual(diagram["internal_lines"][0]["field_id"], 7)
        self.assertEqual(diagram["internal_lines"][0]["kind"], "bsm")

    def test_published_ids_and_line_linkage(self):
        model = self.engine.model("MF-3i-1")
        self.assertEqual(model["field_ids"], [1, 3, 12])
        diagram = self.engine.diagram("T1-1-3")
        self.assertEqual(diagram["field_to_internal_lines"]["56"], ["I1", "I4"])
        self.assertTrue(diagram["internal_lines"][0]["conjugated"])
        self.assertFalse(diagram["internal_lines"][3]["conjugated"])


if __name__ == "__main__":
    unittest.main()

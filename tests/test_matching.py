import copy
import unittest

from matching.catalog import CatalogError, catalog_id_for, validate_catalog
from matching.engine import InvalidFieldError, MatchingEngine
from tests.helpers import fixture_catalog


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = fixture_catalog([(1, 2), (1, 2, 3), (2, 4)])
        cls.engine = MatchingEngine(cls.catalog)

    def test_pairwise_compatibility_does_not_imply_joint_compatibility(self):
        engine = MatchingEngine(fixture_catalog([(1, 2), (1, 3), (2, 3)]))
        for left, right in ((1, 2), (1, 3), (2, 3)):
            self.assertTrue(engine.field_compatibility(left, right)["compatible"])
        result = engine.match([1, 2, 3])
        self.assertEqual(result["status"], "incompatible")
        self.assertFalse(result["can_generate"])
        self.assertIsNone(result["min_additional_fields"])
        self.assertEqual(result["compatible_model_ids"], [])

    def test_full_selection_controls_colors_and_undo_restores_minimal_path(self):
        before = self.engine.match([1])
        self.assertEqual(before["next_fields"]["2"]["color"], "red")
        self.assertEqual(before["next_fields"]["3"]["color"], "green")
        self.assertEqual(before["next_fields"]["4"]["state"], "hidden")
        green_selected = self.engine.match([1, 3])
        self.assertEqual(green_selected["compatible_minimal_model_count"], 0)
        self.assertEqual(green_selected["next_fields"]["2"]["color"], "green")
        self.assertEqual(green_selected["min_additional_fields"], 1)
        self.assertEqual(green_selected["status"], "pending")
        self.assertEqual(self.engine.match([1]), before)

    def test_complete_minimal_model_has_priority_over_possible_extensions(self):
        result = self.engine.match([1, 2])
        self.assertEqual(result["status"], "ready_minimal")
        self.assertEqual(result["generation"]["kind"], "minimal")
        self.assertEqual(result["generation"]["model_ids"], ["FS-1-2"])
        self.assertEqual(result["compatible_model_count"], 2)
        self.assertEqual(result["complete_model_count"], 1)
        self.assertEqual(result["next_fields"]["3"]["color"], "green")

    def test_complete_nonminimal_model(self):
        result = self.engine.match([3, 1, 2])
        self.assertEqual(result["status"], "ready_model")
        self.assertEqual(result["generation"]["kind"], "model")
        self.assertEqual(result["min_additional_fields"], 0)

    def test_complete_subset_does_not_make_superset_selection_complete(self):
        result = self.engine.match([1, 2, 4])
        self.assertEqual(result["status"], "incompatible")
        self.assertEqual(result["complete_model_count"], 0)

    def test_reset_is_initial_and_generation_disabled(self):
        result = self.engine.match([])
        self.assertEqual(result["status"], "initial")
        self.assertFalse(result["can_generate"])
        self.assertIsNone(result["min_additional_fields"])
        self.assertEqual(result["compatible_model_count"], 3)
        self.assertTrue(all(state["state"] == "initial" and state["color"] == "white"
                            for state in result["next_fields"].values()))

    def test_normalizes_order_duplicates_and_conjugates(self):
        self.assertEqual(self.engine.match([2, "1^*", 1, "2^C"]),
                         self.engine.match([1, 2]))

    def test_invalid_fields_raise_clear_errors(self):
        for selection in ([0], [6], [-1], [True], [1.0], ["H"], "12", None):
            with self.subTest(selection=selection), self.assertRaises(InvalidFieldError):
                self.engine.match(selection)

    def test_request_versions_are_echoed(self):
        result = self.engine.match([1], request_id="round-8")
        self.assertEqual(result["request_id"], "round-8")
        self.assertEqual(result["catalog_id"], self.engine.catalog_id)

    def test_duplicate_internal_field_lines_count_once_but_preserve_assignments(self):
        catalog = fixture_catalog([(1, 2), (1, 2)],
                                  tokens_override={1: ["1", "1^*", "2", "H"]})
        engine = MatchingEngine(catalog)
        result = engine.match([1, 2])
        self.assertEqual(result["complete_model_count"], 1)
        self.assertEqual(result["complete_diagram_count"], 2)
        diagram = engine.diagram("T1-1-1")
        self.assertEqual(diagram["field_to_internal_lines"]["1"], ["I1", "I2"])
        self.assertTrue(diagram["internal_lines"][1]["conjugated"])
        self.assertEqual(diagram["internal_lines"][3]["kind"], "sm")

    def test_numbered_field_matching_sm_charges_is_still_a_new_field(self):
        # Fixture field 1 is a scalar with (1,1,-1), rather than the SM fermion e_R.
        self.assertEqual(self.engine.field(1)["sm_quantum_matches"], [])
        result = self.engine.match([1, 2])
        self.assertEqual(result["complete_model_ids"], ["FS-1-2"])

    def test_input_and_returned_records_cannot_mutate_engine_indexes(self):
        catalog = copy.deepcopy(self.catalog)
        engine = MatchingEngine(catalog)
        catalog["models"][0]["field_ids"].clear()
        returned = engine.model("FS-1-2")
        returned["field_ids"].clear()
        self.assertEqual(engine.model("FS-1-2")["field_ids"], [1, 2])
        self.assertEqual(engine.match([1, 2])["status"], "ready_minimal")

    def test_catalog_validates_minimality_even_with_recomputed_hash(self):
        catalog = copy.deepcopy(self.catalog)
        model = next(m for m in catalog["models"] if m["id"] == "FS-1-2-3")
        model["minimal"] = True
        catalog["catalog_id"] = catalog_id_for(catalog)
        with self.assertRaises(CatalogError):
            validate_catalog(catalog)

    def test_catalog_rejects_stale_index_and_incorrect_line_assignment(self):
        for mutation in ("index", "line"):
            catalog = copy.deepcopy(self.catalog)
            if mutation == "index":
                catalog["indexes"]["field_to_models"]["1"] = []
            else:
                catalog["diagrams"][0]["internal_lines"][0]["conjugated"] = True
            catalog["catalog_id"] = catalog_id_for(catalog)
            with self.subTest(mutation=mutation), self.assertRaises(CatalogError):
                validate_catalog(catalog)


if __name__ == "__main__":
    unittest.main()

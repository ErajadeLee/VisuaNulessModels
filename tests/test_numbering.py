import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from matching.catalog import CatalogError, catalog_id_for, validate_catalog, write_catalog
from matching.cli import main
from matching.engine import MatchingEngine
from tests.helpers import fixture_catalog


class PublishedNumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The published suffix deliberately differs from any sorted local rank.
        cls.catalog = fixture_catalog([(1, 2, 3), (1, 2, 3, 4)],
                                      reference_ids={(1, 2, 3): "MF-3i-17"})
        cls.engine = MatchingEngine(cls.catalog)

    def test_published_model_field_is_the_primary_id_and_fs_is_an_alias(self):
        result = self.engine.match([1, 2, 3])
        self.assertEqual(result["complete_model_ids"], ["MF-3i-17"])
        self.assertEqual(result["complete_model_field_ids"], ["MF-3i-17"])
        self.assertEqual(result["complete_model_diagram_ids"], ["T1-1-1"])
        self.assertEqual(result["generation"]["model_ids"], ["MF-3i-17"])
        self.assertEqual(result["generation"]["model_field_ids"], ["MF-3i-17"])
        self.assertEqual(result["generation"]["model_diagram_ids"], ["T1-1-1"])
        model = self.engine.model("FS-1-2-3")
        self.assertEqual(model, self.engine.model_field("MF-3i-17"))
        self.assertEqual(model["id"], "MF-3i-17")
        self.assertEqual(model["internal_id"], "FS-1-2-3")

    def test_both_numbering_levels_link_in_each_direction(self):
        model = self.engine.model_field("MF-3i-17")
        for diagram_id in model["diagram_ids"]:
            diagram = self.engine.model_diagram(diagram_id)
            self.assertEqual(diagram["model_diagram_id"], diagram_id)
            self.assertEqual(diagram["model_field_id"], "MF-3i-17")
            self.assertEqual(diagram["model_id"], model["id"])
        pair = self.engine.field_compatibility(1, 2)
        self.assertEqual(pair["compatible_model_field_ids"], ["MF-3i-17"])
        self.assertEqual(pair["compatible_model_diagram_ids"], ["T1-1-1", "T1-1-2"])

    def test_nonminimal_group_has_no_invented_published_model_field_id(self):
        result = self.engine.match([1, 2, 3, 4])
        self.assertEqual(result["complete_model_field_ids"], [])
        self.assertEqual(result["generation"]["model_field_ids"], [])
        self.assertEqual(result["generation"]["model_diagram_ids"], ["T1-1-2"])
        self.assertIsNone(self.engine.model("FS-1-2-3-4")["model_field_id"])
        self.assertIsNone(self.engine.model_diagram("T1-1-2")["model_field_id"])

    def test_missing_or_changed_published_rows_are_rejected(self):
        changes = {
            "wrong_diagram_id": lambda s: s.replace("T1-1-1&", "T1-1-99&", 1),
            "wrong_assignment": lambda s: s.replace("$1$", "$2$", 1),
            "wrong_minimality": lambda s: s.replace(r"\ding{51}", r"\ding{55}", 1),
            "missing_field_row": lambda s: "\n".join(
                line for line in s.splitlines() if not line.startswith("MF-")),
            "wrong_field_diagram": lambda s: s.replace(
                r"MF-3i-17&1,\,2,\,3&T1-1-1", r"MF-3i-17&1,\,2,\,3&T1-1-2"),
        }
        for name, transform in changes.items():
            with self.subTest(change=name), self.assertRaises(CatalogError):
                fixture_catalog([(1, 2, 3), (1, 2, 3, 4)],
                                reference_ids={(1, 2, 3): "MF-3i-17"},
                                supplementary_transform=transform)

    def test_stale_alias_and_diagram_field_number_are_rejected(self):
        for change in ("alias", "diagram"):
            catalog = copy.deepcopy(self.catalog)
            if change == "alias":
                catalog["indexes"]["model_aliases"]["FS-1-2-3"] = "FS-1-2-3-4"
            else:
                catalog["diagrams"][0]["model_field_id"] = "MF-3i-99"
            catalog["catalog_id"] = catalog_id_for(catalog)
            with self.subTest(change=change), self.assertRaises(CatalogError):
                validate_catalog(catalog)

    def test_cli_queries_both_published_numbering_levels(self):
        with tempfile.TemporaryDirectory(prefix="0nbb-numbering-test-") as directory:
            path = Path(directory) / "catalog.json"
            write_catalog(self.catalog, path)
            for command, identifier in (("model-field", "MF-3i-17"),
                                        ("model-diagram", "T1-1-1")):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["--catalog", str(path), command, identifier])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output.getvalue())["id"], identifier)
        for identifier in ("FS-1-2-3", "T1-1-1", "MF-3i-999"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.engine.model_field(identifier)


CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


@unittest.skipUnless(CATALOG.is_file(), "Run python -m matching build first")
class RealNumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MatchingEngine.from_file(CATALOG)

    def test_all_710_minimal_groups_use_published_mf_ids(self):
        models = self.engine._catalog["models"]
        minimal = [model for model in models if model["minimal"]]
        self.assertEqual(len(minimal), 710)
        for model in minimal:
            with self.subTest(model_id=model["id"]):
                self.assertEqual(model["id"], model["model_field_id"])
                self.assertEqual(model["id"], model["reference_id"])
                self.assertTrue(model["id"].startswith("MF-"))
                self.assertEqual(self.engine.model(model["internal_id"])["id"], model["id"])

    def test_all_5280_model_diagrams_keep_original_t_ids_and_links(self):
        diagrams = self.engine._catalog["diagrams"]
        self.assertEqual(len(diagrams), 5280)
        for diagram in diagrams:
            model = self.engine._model_lookup[diagram["model_id"]]
            with self.subTest(diagram_id=diagram["id"]):
                self.assertEqual(diagram["model_diagram_id"], diagram["id"])
                self.assertTrue(diagram["id"].startswith("T"))
                self.assertEqual(diagram["model_field_id"], model["model_field_id"])

    def test_user_example_has_exact_published_ids(self):
        result = self.engine.match([1, 52, 56])
        self.assertEqual(result["complete_model_ids"], ["MF-3i-23"])
        self.assertEqual(result["complete_model_field_ids"], ["MF-3i-23"])
        self.assertEqual(result["complete_model_diagram_ids"], [
            "T1-1-3", "T1-1-9", "T1-1-17", "T1-1-31", "T4-1-3", "T4-1-14", "T4-1-23"])
        nonminimal = self.engine.match([13, 30, 40, 48])
        self.assertEqual(nonminimal["complete_model_field_ids"], [])
        self.assertEqual(nonminimal["complete_model_diagram_ids"], ["T1-1-41", "T1-1-56"])


if __name__ == "__main__":
    unittest.main()

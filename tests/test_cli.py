import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from matching.catalog import write_catalog
from matching.cli import main
from tests.helpers import fixture_catalog


class CliTests(unittest.TestCase):
    def test_json_match_and_invalid_field_exit_code(self):
        with tempfile.TemporaryDirectory(prefix="0nbb-cli-test-") as directory:
            path = Path(directory) / "catalog.json"
            write_catalog(fixture_catalog([(1, 2)]), path)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(["--catalog", str(path), "match",
                                  "--fields", "1", "2", "--request-id", "test"])
            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "ready_minimal")
            self.assertEqual(result["request_id"], "test")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                exit_code = main(["--catalog", str(path), "match", "--fields", "999"])
            self.assertEqual(exit_code, 2)
            self.assertIn("Unknown field ID", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

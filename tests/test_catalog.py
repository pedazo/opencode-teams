import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import opencode_catalog as catalog


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "fake-opencode"
        self.executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            "from urllib.parse import parse_qs, urlsplit\n"
            "assert sys.argv[1:3] == ['api', 'get']\n"
            "query = parse_qs(urlsplit(sys.argv[3]).query)\n"
            "assert query['location[directory]'] == [str(pathlib.Path.cwd())]\n"
            "print(pathlib.Path('catalog.json').read_text())\n")
        self.executable.chmod(0o755)
        self.args = argparse.Namespace(project=str(self.root), opencode_bin=str(self.executable), provider=None,
                                       model=None, variant=None, interactive=True)
        self.data = {"location": {"directory": str(self.root)}, "data": [
            {"enabled": True, "providerID": "openai", "id": "sol", "variants": [{"id": "high"}, {"id": "low"}]},
            {"enabled": False, "providerID": "other", "id": "disabled", "variants": []}]}

    def discover(self):
        (self.root / "catalog.json").write_text(json.dumps(self.data))
        return catalog.discover_once(self.args, 5)

    def test_cli_roundtrip(self):
        self.assertEqual(self.discover(), {"openai/sol": ("high", "low")})

    def test_wrong_location(self):
        self.data["location"]["directory"] = "/wrong"
        with self.assertRaises(catalog.ConfigError):
            self.discover()

    def test_duplicates(self):
        self.data["data"].append(self.data["data"][0])
        with self.assertRaises(catalog.ConfigError):
            self.discover()

    def test_invalid_variants(self):
        self.data["data"][0]["variants"] = [{"id": "high\nmodel: bad"}]
        with self.assertRaises(catalog.ConfigError):
            self.discover()

    def test_provider_filter(self):
        self.args.provider = "other"
        self.assertEqual(self.discover(), {})

    def test_numeric_model_and_variant(self):
        with patch("builtins.input", side_effect=["1", "2"]), redirect_stdout(io.StringIO()):
            self.assertEqual(catalog.choose_model(self.args, ["openai/sol"]), "openai/sol")
            self.assertEqual(catalog.choose_variant(self.args, "openai/sol", ("high", "low")), "high")

    def test_no_variant(self):
        with patch("builtins.input", return_value="1"), redirect_stdout(io.StringIO()):
            self.assertIsNone(catalog.choose_variant(self.args, "openai/sol", ("high",)))

    def test_cancel(self):
        with patch("builtins.input", return_value="Q"), redirect_stdout(io.StringIO()):
            with self.assertRaises(catalog.Cancelled):
                catalog.choose_model(self.args, ["openai/sol"])

    def test_unknown_model_rejected(self):
        self.args.model = "openai/unknown"
        with self.assertRaises(catalog.ConfigError):
            catalog.choose_model(self.args, ["openai/sol"])

    def test_no_variant_noninteractive(self):
        self.args.interactive = False
        self.assertIsNone(catalog.choose_variant(self.args, "openai/sol", ("high",)))


if __name__ == "__main__":
    unittest.main()

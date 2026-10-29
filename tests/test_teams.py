import argparse
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import teams


class TeamsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(teams.ROOT / "templates", self.root / "templates")
        self.target = {"scope": "project", "config_dir": str(self.root / "project" / ".opencode")}
        self.registry = {"version": 1, "teams": {
            "openai": {"models": {}, "targets": [self.target]}}}
        self.profile = self.registry["teams"]["openai"]

    def run_cli(self, arguments, inputs=None):
        with patch.object(teams, "ROOT", self.root), redirect_stdout(io.StringIO()), patch("builtins.input", side_effect=inputs or []):
            return teams.main(arguments)

    def deploy(self):
        changes = teams.installation_changes(self.root, "openai", self.profile, self.profile["targets"])
        with redirect_stdout(io.StringIO()):
            teams.transact(self.root, self.registry, changes)

    def test_names(self):
        self.assertEqual(teams.team_name("team-openai"), "openai")
        self.assertEqual(teams.team_name("team-team-openai"), "openai")
        for name in ("../bad", "a/b", "a--b", "Upper", "", "a\n"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                teams.team_name(name)

    def test_render_all_and_team_isolation(self):
        for role in teams.ROLES:
            content = teams.render_agent(self.root, "openai", role, {}).decode()
            self.assertNotIn("{{team}}", content)
            self.assertNotIn("team-anthropic", content)
        master = teams.render_agent(self.root, "openai", "master", {}).decode()
        for role in teams.ROLES:
            if role != "master":
                self.assertIn(f'resource: "team-openai-{role}"', master)

    def test_behavior_preserved_except_names(self):
        for role in teams.ROLES:
            original = (self.root / "templates" / f"{role}.md").read_text()
            rendered = teams.render_agent(self.root, "openai", role, {}).decode()
            self.assertEqual(rendered, original.replace("{{team}}", "team-openai"))
            self.assertEqual(len(original.splitlines()), len(rendered.splitlines()))
            self.assertEqual(original.count("effect: deny"), rendered.count("effect: deny"))
            self.assertEqual(original.count("effect: allow"), rendered.count("effect: allow"))

    def test_templates_are_named_by_role(self):
        self.assertEqual(
            {path.name for path in (self.root / "templates").iterdir()},
            {f"{role}.md" for role in teams.ROLES},
        )

    def test_master_model_and_command(self):
        models = {"master": "openai/sol#high"}
        self.assertIn(b"model: openai/sol#high\n", teams.render_agent(self.root, "openai", "master", models))
        command = teams.render_command("openai", models)
        self.assertIn(b"agent: team-openai-master", command)
        self.assertIn(b"model: openai/sol#high", command)
        self.assertIn(b"subagent: false", command)
        self.assertNotIn(b"model:", teams.render_command("openai", {}))

    def test_install_writes_ten_files_and_registry(self):
        self.deploy()
        for path in teams.managed_paths(self.target, "openai"):
            self.assertTrue(path.is_file())
        self.assertEqual(teams.load_registry(self.root), self.registry)

    def test_dry_run(self):
        changes = teams.installation_changes(self.root, "openai", self.profile, self.profile["targets"])
        with redirect_stdout(io.StringIO()):
            teams.transact(self.root, self.registry, changes, dry_run=True)
        self.assertFalse((self.root / "registry.json").exists())
        self.assertFalse(Path(self.target["config_dir"]).exists())

    def test_update_overwrites_and_preserves_models(self):
        self.profile["models"] = {"master": "openai/sol#high", "reviewer": "anthropic/claude#low"}
        self.deploy()
        master = teams.managed_paths(self.target, "openai")[0]
        master.write_text("manual edit")
        template = self.root / "templates" / "master.md"
        template.write_text(template.read_text() + "\nNew central behavior.\n")
        self.assertEqual(self.run_cli(["install", "--all-teams"]), 0)
        self.assertIn("New central behavior", master.read_text())
        self.assertIn("model: openai/sol#high", master.read_text())
        self.assertEqual(teams.load_registry(self.root)["teams"]["openai"]["models"], self.profile["models"])

    def test_multiple_teams_and_destinations(self):
        for name in ("openai", "anthropic"):
            for project in ("one", "two"):
                self.assertEqual(self.run_cli(["install", "--team", name, "--scope", "project", "--project", str(self.root / project)]), 0)
        self.assertEqual(self.run_cli(["install", "--all-teams"]), 0)
        registry = teams.load_registry(self.root)
        for name in registry["teams"]:
            self.assertEqual(len(registry["teams"][name]["targets"]), 2)
            for target in registry["teams"][name]["targets"]:
                for path in teams.managed_paths(target, name):
                    self.assertTrue(path.exists())

    def test_configure_master_sync(self):
        self.deploy()
        with patch.object(teams.catalog, "discover_models", return_value={"openai/sol": ("high", "low")}):
            self.assertEqual(self.run_cli(["models", "--team", "openai", "--agent", "master", "--model", "openai/sol", "--variant", "high"]), 0)
        for path in (teams.managed_paths(self.target, "openai")[0], teams.managed_paths(self.target, "openai")[-1]):
            self.assertIn("model: openai/sol#high", path.read_text())

    def test_interactive_wizard(self):
        self.deploy()
        with patch.object(teams.catalog, "discover_models", return_value={"openai/sol": ("high", "low")}):
            self.assertEqual(self.run_cli(["models"], inputs=["1", "master", "1", "1", "2", "yes"]), 0)
        profile = teams.load_registry(self.root)["teams"]["openai"]
        self.assertEqual(profile["models"]["master"], "openai/sol#high")

    def test_interactive_all_and_role_name_agent_selection(self):
        with patch("builtins.input", return_value="all"), redirect_stdout(io.StringIO()):
            self.assertEqual(teams.choose_agents(self.profile), list(teams.ROLES))
        with patch("builtins.input", return_value="master,3"), redirect_stdout(io.StringIO()):
            self.assertEqual(teams.choose_agents(self.profile), ["master", "planner"])

    def test_interactive_subset_provider_filter_and_current_selections(self):
        self.profile["models"] = {
            "planner": "anthropic/claude#low",
            "reviewer": "openai/sol",
        }
        self.deploy()
        models = {"anthropic/claude": ("low",), "openai/sol": ("high",)}
        output = io.StringIO()
        prompts = []
        answers = iter(["1,3,5", "2", "1", "1", "yes"])

        def respond(prompt):
            prompts.append(prompt)
            return next(answers)

        with patch.object(teams, "ROOT", self.root):
            with patch.object(teams.catalog, "discover_models", return_value=models), patch(
                    "builtins.input", side_effect=respond), redirect_stdout(output):
                self.assertEqual(teams.main(["models", "--team", "openai"]), 0)
        profile = teams.load_registry(self.root)["teams"]["openai"]
        self.assertEqual(profile["models"]["master"], "openai/sol")
        self.assertEqual(profile["models"]["planner"], "openai/sol")
        self.assertEqual(profile["models"]["developer"], "openai/sol")
        self.assertEqual(profile["models"]["reviewer"], "openai/sol")
        text = output.getvalue()
        for index, role in enumerate(teams.ROLES, 1):
            self.assertIn(f"{index}. {role} — current model:", text)
        self.assertIn("current model: inherit session model; reasoning: no variant", text)
        self.assertIn("current model: anthropic/claude; reasoning: low", text)
        self.assertIn("current model: openai/sol; reasoning: no variant", text)
        self.assertIn("1. openai/sol", text)
        self.assertNotIn("1. anthropic/claude", text)
        self.assertIn("team-openai: master, planner, developer -> openai/sol; reasoning: no variant", text)
        self.assertLess(prompts.index("Provider ID or number (0/q/quit cancels): "),
                        prompts.index("Model ID or number (0/q/quit cancels): "))
        self.assertLess(prompts.index("Reasoning variant ID or number (blank for no variant): "),
                        prompts.index("Apply changes? [y/N]: "))

    def test_cancel_leaves_registry_and_agents_unchanged(self):
        self.deploy()
        original = (self.root / "registry.json").read_bytes()
        master = teams.managed_paths(self.target, "openai")[0].read_bytes()
        with patch.object(teams.catalog, "discover_models", return_value={"openai/sol": ("high",)}):
            self.assertEqual(self.run_cli(["models", "--team", "openai"], inputs=["master", "1", "1", "2", "no"]), 0)
        self.assertEqual((self.root / "registry.json").read_bytes(), original)
        self.assertEqual(teams.managed_paths(self.target, "openai")[0].read_bytes(), master)

    def test_global_scope_respects_xdg(self):
        destination = self.root / "config"
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(destination)}):
            self.assertEqual(self.run_cli(["install", "--team", "patata"]), 0)
        self.assertTrue((destination / "opencode" / "agents" / "team-patata-master.md").exists())
        self.assertTrue((destination / "opencode" / "commands" / "team-patata.md").exists())

    def test_invalid_variant_has_no_writes(self):
        self.deploy()
        original = (self.root / "registry.json").read_bytes()
        with patch.object(teams.catalog, "discover_models", return_value={"openai/sol": ("high",)}):
            self.assertEqual(self.run_cli(["models", "--team", "openai", "--all", "--model", "openai/sol", "--variant", "invalid"]), 2)
        self.assertEqual((self.root / "registry.json").read_bytes(), original)

    def test_inherit_clears_agent_and_command(self):
        self.profile["models"]["master"] = "openai/sol#high"
        self.deploy()
        self.assertEqual(self.run_cli(["models", "--team", "openai", "--agent", "master", "--inherit"]), 0)
        for path in (teams.managed_paths(self.target, "openai")[0], teams.managed_paths(self.target, "openai")[-1]):
            self.assertNotIn("model:", path.read_text())

    def test_uninstall_keeps_profile(self):
        self.deploy()
        self.assertEqual(self.run_cli(["install", "--team", "openai", "--uninstall"]), 0)
        self.assertIn("openai", teams.load_registry(self.root)["teams"])
        for path in teams.managed_paths(self.target, "openai"):
            self.assertFalse(path.exists())

    def test_forget_removes_profile(self):
        self.deploy()
        self.assertEqual(self.run_cli(["install", "--team", "openai", "--uninstall", "--forget"]), 0)
        self.assertNotIn("openai", teams.load_registry(self.root)["teams"])

    def test_caught_failure_rolls_back(self):
        self.deploy()
        original = (self.root / "registry.json").read_bytes()
        paths = teams.managed_paths(self.target, "openai")
        previous = {path: path.read_bytes() for path in paths}
        real_write = teams.atomic_write
        calls = []
        def fail_once(path, content):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("Simulated failure")
            real_write(path, content)
        with patch.object(teams, "atomic_write", side_effect=fail_once), redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                teams.transact(self.root, self.registry, {path: b"changed" for path in paths})
        self.assertEqual((self.root / "registry.json").read_bytes(), original)
        for path in paths:
            self.assertEqual(path.read_bytes(), previous[path])

    def test_symlink_not_followed(self):
        outside = self.root / "outside"
        outside.write_text("keep")
        linked = self.root / "linked"
        linked.symlink_to(outside)
        with self.assertRaises(ValueError):
            teams.transact(self.root, self.registry, {linked: b"changed"})
        self.assertEqual(outside.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Central, independent manager for named OpenCode teams (Python 3.9+)."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import opencode_catalog as catalog

ROOT = Path(__file__).resolve().parent.parent
ROLES = (
    "master", "explorer", "planner", "quick-fixer", "developer",
    "operator", "reviewer", "verifier", "technical-writer",
)


def team_name(value):
    while value.startswith("team-"):
        value = value.removeprefix("team-")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) or len(value) > 48:
        raise ValueError("Team name: lowercase letters, numbers and single hyphens (max 48).")
    return value


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing to replace symbolic link: {path}")
    fd, temporary = tempfile.mkstemp(prefix=".team-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def registry_lock(root):
    with (root / ".registry.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def load_registry(root):
    path = root / "registry.json"
    if not path.exists():
        return {"version": 1, "teams": {}}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("teams"), dict):
        raise ValueError("Unsupported or invalid registry.")
    # Validate before using persisted names as filesystem paths.
    for name, profile in data["teams"].items():
        if team_name(name) != name or not isinstance(profile, dict):
            raise ValueError("Invalid team profile.")
        if not isinstance(profile.get("models"), dict) or not isinstance(profile.get("targets"), list):
            raise ValueError("Invalid team models or targets.")
        for role, selection in profile["models"].items():
            if role not in ROLES or not isinstance(selection, str) or not catalog.MODEL_REF_RE.fullmatch(selection):
                raise ValueError(f"Invalid model selection for {name}/{role}.")
        for target in profile["targets"]:
            if not isinstance(target, dict) or target.get("scope") not in ("user", "project") or not isinstance(target.get("config_dir"), str) or not Path(target["config_dir"]).is_absolute():
                raise ValueError("Invalid installation target.")
    return data


def render_agent(root, name, role, models):
    if role not in ROLES:
        raise ValueError(f"Unknown agent role: {role}")
    text = (root / "templates" / f"{role}.md").read_text()
    text = text.replace("{{team}}", f"team-{name}")
    if role in models:
        text = text.replace("---\n", f"---\nmodel: {models[role]}\n", 1)
    return text.encode()


def template_revision(root):
    digest = hashlib.sha256()
    for role in ROLES:
        digest.update((root / "templates" / f"{role}.md").read_bytes())
    return digest.hexdigest()


def render_command(name, models):
    lines = ["---", f"description: Run a task with team-{name}.",
             f"agent: team-{name}-master", "subagent: false"]
    if "master" in models:
        lines.append(f"model: {models['master']}")
    lines += ["---", "", "$ARGUMENTS", ""]
    return "\n".join(lines).encode()


def target_from_args(args):
    if args.scope == "user":
        directory = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "opencode"
    else:
        directory = Path(args.project).expanduser().resolve() / ".opencode"
    return {"scope": args.scope, "config_dir": str(directory.absolute())}


def managed_paths(target, name):
    directory = Path(target["config_dir"])
    return [directory / "agents" / f"team-{name}-{role}.md" for role in ROLES] + [
        directory / "commands" / f"team-{name}.md"]


def installation_changes(root, name, profile, targets):
    changes = {}
    revision = template_revision(root)
    for target in targets:
        paths = managed_paths(target, name)
        for role, path in zip(ROLES, paths):
            changes[path] = render_agent(root, name, role, profile["models"])
        changes[paths[-1]] = render_command(name, profile["models"])
        target["revision"] = revision
    return changes


def transact(root, registry, changes, dry_run=False):
    changes = dict(changes)
    changes[root / "registry.json"] = (json.dumps(registry, indent=2, sort_keys=True) + "\n").encode()
    originals = {}
    for path, content in changes.items():
        # Reject linked directories as well as linked destination files.
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError(f"Symbolic links are not managed: {path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"Not a regular file: {path}")
        originals[path] = path.read_bytes() if path.exists() else None
        print(f"{'Delete' if content is None else 'Write'} {path}")
    if dry_run:
        print("Dry run: no agents, commands or registry changed.")
        return
    completed = []
    try:
        for path, content in changes.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, content)
            completed.append(path)
    except BaseException:
        for path in reversed(completed):
            if originals[path] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, originals[path])
        raise


def choose(prompt, choices):
    for index, value in enumerate(choices, 1):
        print(f"  {index}. {value}")
    answer = input(prompt).strip()
    if answer.lower() in ("0", "q", "quit"):
        raise catalog.Cancelled()
    if answer.isdigit() and 1 <= int(answer) <= len(choices):
        return choices[int(answer) - 1]
    if answer in choices:
        return answer
    raise ValueError("Invalid selection.")


def select_team(args, registry, create=False):
    if args.team:
        name = team_name(args.team)
    elif create:
        print("Registered teams: " + (", ".join(registry["teams"]) or "none"))
        name = team_name(input("Team name (without team-): ").strip())
    else:
        name = choose("Team: ", sorted(registry["teams"]))
    if name not in registry["teams"]:
        if not create:
            raise ValueError(f"Team not registered: {name}")
        registry["teams"][name] = {"models": {}, "targets": []}
    return name


def install(args, registry):
    if args.all_teams:
        if args.team:
            raise ValueError("Use --team or --all-teams, not both.")
        names = list(registry["teams"])
        if not names:
            raise ValueError("No registered teams.")
    else:
        if not args.team and not args.uninstall and not args.update and sys.stdin.isatty() and registry["teams"]:
            action = choose("Install action: ", ["create-or-install", "update-team", "update-all"])
            if action == "update-all":
                args.all_teams = True
                return install(args, registry)
            if action == "update-team":
                args.team = choose("Team: ", sorted(registry["teams"]))
                args.update = True
        names = [select_team(args, registry, create=not args.uninstall and not args.update)]
    if args.forget and not args.uninstall:
        raise ValueError("--forget requires --uninstall.")
    changes = {}
    for name in names:
        profile = registry["teams"][name]
        if args.uninstall:
            # No scope flags means remove all registered destinations for this team.
            targets = profile["targets"]
            if args.scope is not None:
                destination = target_from_args(args)
                targets = [t for t in targets if t["config_dir"] == destination["config_dir"]]
            for target in targets:
                changes.update({path: None for path in managed_paths(target, name)})
            profile["targets"] = [t for t in profile["targets"] if t not in targets]
            if args.forget:
                if profile["targets"]:
                    raise ValueError("Uninstall all destinations before forgetting a team.")
                del registry["teams"][name]
        else:
            if not args.all_teams and not args.update:
                args.scope = args.scope or "user"
                target = target_from_args(args)
                if not any(t["config_dir"] == target["config_dir"] for t in profile["targets"]):
                    profile["targets"].append(target)
            changes.update(installation_changes(ROOT, name, profile, profile["targets"]))
    transact(ROOT, registry, changes, args.dry_run)


def configure(args, registry):
    name = select_team(args, registry)
    profile = registry["teams"][name]
    if args.all and args.agent:
        raise ValueError("Use --agent or --all, not both.")
    if args.all:
        roles = list(ROLES)
    elif args.agent:
        roles = args.agent
        if any(role not in ROLES for role in roles):
            raise ValueError("Unknown agent role.")
    else:
        args.interactive = True
        selected = choose("Agent role: ", list(ROLES) + ["all"])
        roles = list(ROLES) if selected == "all" else [selected]
    if args.inherit:
        if args.model or args.variant:
            raise ValueError("--inherit cannot be combined with --model or --variant.")
        selection = None
    else:
        models = catalog.discover_models(args)
        args.interactive = not args.model or args.interactive
        model = catalog.choose_model(args, list(models))
        variant = catalog.choose_variant(args, model, models[model])
        selection = model + ("#" + variant if variant else "")
    print(f"team-{name}: {', '.join(roles)} -> {selection or 'inherit session model'}")
    if args.interactive and not catalog.confirm_interactive():
        raise catalog.Cancelled()
    for role in roles:
        if selection is None:
            profile["models"].pop(role, None)
        else:
            profile["models"][role] = selection
    changes = installation_changes(ROOT, name, profile, profile["targets"])
    transact(ROOT, registry, changes, args.dry_run)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="action", required=True)
    for action in ("install", "models", "list"):
        command = commands.add_parser(action)
        command.add_argument("--team", help="Team slug, with or without team- prefix")
        command.add_argument("--project", default=os.getcwd(), help="Project/catalog context")
        command.add_argument("--dry-run", action="store_true")
        if action == "install":
            command.add_argument("--scope", choices=("user", "project"))
            command.add_argument("--all-teams", action="store_true")
            command.add_argument("--update", action="store_true", help="Update registered destinations only")
            command.add_argument("--uninstall", action="store_true")
            command.add_argument("--forget", action="store_true")
        if action == "models":
            command.add_argument("--agent", action="append", help="Role; repeat for multiple roles")
            command.add_argument("--all", action="store_true", help="All nine roles, including master")
            command.add_argument("--model")
            command.add_argument("--variant")
            command.add_argument("--inherit", action="store_true", help="Clear configured model and variant")
            command.add_argument("--interactive", action="store_true")
            command.add_argument("--provider")
            command.add_argument("--opencode-bin", default="opencode")
            command.set_defaults(custom_variant=None)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        with registry_lock(ROOT):
            registry = copy.deepcopy(load_registry(ROOT))
            if args.action == "install":
                install(args, registry)
            elif args.action == "models":
                configure(args, registry)
            else:
                teams = registry["teams"]
                if args.team:
                    name = team_name(args.team)
                    teams = {name: teams[name]}
                print(json.dumps(teams, indent=2, sort_keys=True))
        return 0
    except catalog.Cancelled:
        print("cancelled")
        return 0
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, EOFError, catalog.ConfigError) as error:
        print(f"teams: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

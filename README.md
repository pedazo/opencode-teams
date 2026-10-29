# Named OpenCode teams

Independent agent system with centrally managed team names, models, reasoning
variants, agents and launch commands. Python 3.9+ on Linux/macOS; no external
Python dependencies or runtime dependency on another agent project.

## Quick start

```sh
# Interactive installer: create/install, update one, or update all teams.
sh install

# Install globally (default), with any lowercase team name.
sh install --team openai
sh install --team anthropic

# Or install into a specific project.
sh install --team patata --scope project --project /path/to/project

# Choose role, discovered model, and model-specific reasoning variant.
sh set-models --team openai

# Configure the master too. Use an exact ID and variant from your V2 catalog.
sh set-models --team openai --agent master --model PROVIDER/MODEL --variant VARIANT

# Give all nine agents the same model, including the master.
sh set-models --team openai --all --model PROVIDER/MODEL

# Clear the master's configured model and reasoning (inherit session choice).
sh set-models --team openai --agent master --inherit

# Update common behavior everywhere, retaining each team's model selections.
sh install --all-teams
sh install --team openai --update

# Inspect the central registry.
python3 bin/teams.py list

# Remove all registered installations, retaining the model profile.
sh install --team patata --uninstall
# Also delete the profile.
sh install --team patata --uninstall --forget
```

`--dry-run` previews installation, configuration and uninstallation. The model
wizard confirms before writing; non-interactive options apply directly. `--agent`
accepts a role and can be repeated. A model-only non-interactive selection removes
the previous reasoning variant. `--project` on `set-models` selects the catalog
context; configured models must be available wherever that team is used.

## Launch commands

In OpenCode's command interface:

```text
/team-openai Implement the requested change
/team-anthropic Review this implementation
```

Each command selects its team's master and the configured model/variant, then
submits your task in the current session. You can subsequently change the model
manually. Invoking the command again reapplies its configured model. A master
without a configured model leaves the session model unchanged. Merely choosing
the agent in the agent selector does not apply its configured model in V2.

These are native OpenCode commands; whether another client exposes those commands
depends on that client's UI. This installer does not modify OpenChamber.

## Roles

- `master`: local development and optional coordination.
- `explorer`: read-only repository reconnaissance.
- `planner`: criteria-driven plans for complex changes.
- `quick-fixer`: small, clearly scoped implementation.
- `developer`: non-trivial implementation and relevant tests.
- `operator`: a clearly specified operational action.
- `reviewer`: independent, read-only review and security checks.
- `verifier`: focused tests, lint, builds and other checks.
- `technical-writer`: documentation aligned with actual behavior.

Agent IDs use `team-NAME-ROLE`. Each master can delegate only to its own eight
specialists. Task approval, credential handling, Git publication and
no-further-delegation rules apply to every team.

## Single source of truth

- `templates/`: role-named prompts (`master.md`, `explorer.md`, etc.). The
  `{{team}}` placeholder resolves to the selected team's prefix in internal agent
  references and permissions. Edit these templates to change behavior centrally.
- `registry.json`: created on the first real operation. Stores each team's model
  selections, registered installation scopes/destinations and template revision.
  Keep this file to preserve your profiles. It contains no provider credentials.
- `bin/teams.py`: installer, central configurator and registry manager.
- `bin/opencode_catalog.py`: independent V2 discovery and model/variant selection
  adapter.

Global files go to `$XDG_CONFIG_HOME/opencode/{agents,commands}` (default
`~/.config/opencode/`); project files go to `PROJECT/.opencode/{agents,commands}`.
The same profile can be installed in several destinations. Model changes rewrite
all registered installations of that team, also refreshing central behavior.

Reinstallation **overwrites** installed files without preserving manual edits or
creating backups. Only the selected team's nine agents and its command are
managed; other agents and OpenCode configuration are untouched. Do not manage the
same installation from multiple copies of this project. Avoid installing the same
team globally and locally with different external configurations, since OpenCode
merges definitions by ID.

Operations serialize through a central lock and atomically replace individual
files, writing the registry last. Caught errors and Ctrl+C roll back completed
writes. Power loss/SIGKILL are not batch-atomic: rerun installation to reconcile.
Dry runs may create the lock file, but no agents, commands or registry.

## Verification

```sh
sh -n install
sh -n set-models
python3 -B -m unittest discover -s tests -v
```

OpenCode V2 references: https://opencode.ai/v2/docs/agents and
https://opencode.ai/v2/docs/commands#execution.

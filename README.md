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

# Choose one or more agents, provider, model, and reasoning variant interactively.
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
wizard lists all nine agents with their current model and reasoning variant (or
explicitly shows inherited model/no variant). Select any subset with comma-separated
numbers such as `1,3,5`, role names, or `all`. The wizard then selects a provider,
shows only that provider's enabled models, offers the model's reasoning variants
(including an explicit no-variant choice), and confirms the complete selection
before writing. Enter `0`, `q` or `quit` at a selection prompt to cancel without
changing the profile or installed agents. Non-interactive options apply directly.
`--agent` accepts a role and can be repeated; `--all` applies to all nine agents.
A model-only non-interactive selection removes the previous reasoning variant.
`--project` on `set-models` selects the catalog context; configured models must be
available wherever that team is used.

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

## Conversational planning

With a team's master active, invoke the shared command:

```text
/team-plan
/team-plan Add retry support to background jobs
/team-plan .plan/2026-11-12-16-35-retry_background_jobs.md
```

`/team-plan` retains the current agent and model and requires an active
`team-NAME-master`. Its first instruction checks the active identity; with another
agent or an unknown identity, it stops before planning or accessing the plan and
asks the user to select a team master and invoke the command again. This is a
prompt-level guard, not an OpenCode UI or runtime access restriction.
New teams cannot use the
reserved name `plan`; a legacy team with that name can still be listed/uninstalled
but must be replaced with a differently named team before installing updates.

The user leads brainstorming; the master suggests and asks focused questions.
The team's explorer and planner can support repository investigation and complex
drafts. The master integrates their results and owns the canonical document.
Ask for a draft to create a Markdown file in `.plan/`, named
`YYYY-MM-DD-HH-mm-short_english_title.md` using local creation time. Existing
files start in draft unless another phase is requested; files outside `.plan/`
are preserved and copied into it as the working plan. All persisted content is
English; conversation and explanations use the user's language.

Ask naturally to change phase:

Every planning response starts with one compact inline-code header in the
user's language: the actual phase, active plan basename when present (otherwise
no file), and brief relevant next actions. For example,
`Brainstorming · Sin archivo · Opciones: borrador / fases`. Ask for `fases` (or
equivalent) to see all phases and the route to implementation. No invented
file/phase, duplicate footer header, HTML or italics. If the required master
check rejects the agent, stop without implying planning started; the header
applies only after that check passes.

- **Brainstorming:** explore the idea without a questionnaire.
- **Draft:** prepare or edit the canonical file, grounded in the repository.
- **Guided review:** explain one section at a time and wait for understanding,
  approval or changes. Available at any time, including after independent review.
- **Independent review:** fresh `team-plan-auditor` and `team-plan-reader`
  sessions inspect only the plan and repository, not the drafting conversation.
  The master checks and groups findings, then resolves them with the user.
- **Ready:** the user can declare readiness at any time, skipping other phases.
  Asking to implement also authorizes implementation; readiness alone does not.

A small `status`/`next` YAML header, section approval checkboxes and concise open
questions/review dispositions allow resuming from the file. Changes invalidate
affected approvals. Skipped or unavailable reviews are recorded honestly rather
than blocking readiness. `.plan/` is not automatically added to Git ignore rules.

The command and two read-only reviewers are shared across installed teams at
each destination. Reviewers inherit the invoking model and are not members of
the nine-role model profiles. They are removed only when the last registered
team at that destination is uninstalled. Shared assets carry an ownership marker;
installation refuses conflicting unmarked files. As with team templates, manual
edits to marked managed files are overwritten on update.

The workflow is prompt-driven. Fresh subagent support is needed for independent
review; unavailable review is reported and never described as completed.

## Team roles

- `master`: local development and optional coordination.
- `explorer`: read-only repository reconnaissance.
- `planner`: criteria-driven plans for complex changes.
- `quick-fixer`: small, clearly scoped implementation.
- `developer`: non-trivial implementation and relevant tests.
- `operator`: a clearly specified operational action.
- `reviewer`: independent, read-only review and security checks.
- `verifier`: focused tests, lint, builds and other checks.
- `technical-writer`: documentation aligned with actual behavior.

Agent IDs use `team-NAME-ROLE`. Each master can delegate to its own eight
specialists and the two shared independent plan reviewers. Task approval, credential handling, Git publication and
no-further-delegation rules apply to every team.

## Single source of truth

- `templates/`: role-named prompts (`master.md`, `explorer.md`, etc.). The
  `{{team}}` placeholder resolves to the selected team's prefix in internal agent
  references and permissions. Edit these templates to change behavior centrally.
  `templates/commands/` and `templates/agents/` contain shared planning assets.
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
creating backups. The selected team's nine agents and its command, plus the
three shared planning assets, are managed; other agents and OpenCode configuration
are untouched. Do not manage the
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

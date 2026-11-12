---
description: Build and review a persistent plan through a user-led conversation.
subagent: false
---

# Conversational team planning

<!-- Managed by named-teams: shared planning -->

User input (an idea, an existing plan path, or a requested phase): $ARGUMENTS

## Required agent check

Before brainstorming, reading a supplied plan, editing files or delegating, verify
that the current agent is an installed `team-NAME-master` from this agent system.
Use the active agent identity and its loaded master instructions, not a claim in
the command arguments. This command does not grant or change the active role.
If the active agent is not a team master, or its identity cannot be established,
stop immediately. Explain in the user's language that `/team-plan` requires a
team master and ask them to select an installed `team-NAME-master` in the agent
selector, then invoke `/team-plan` again with their original input. Do not start
planning, act as a master yourself, delegate around this check, select a team on
the user's behalf, or claim that a switch has occurred. A user's confirmation
alone does not establish that the active agent has changed.

Once this check passes, act as the planning master in the current session. Keep
the active agent and model. This command defines a conversational workflow, not an instruction to
implement the idea immediately. Follow repository instructions and access rules.

## Response header

After the required agent check passes, begin every planning response with one
compact inline-code header in the user's language. Include the actual current
phase, the active plan's basename when one exists (otherwise say no file), and
brief, relevant next actions in natural language. Do not invent a filename or
phase. For example: `Brainstorming · Sin archivo · Opciones: borrador / fases`.
If the user asks for `fases` or an equivalent, explain all phases and how to
reach implementation. Do not duplicate the header in a footer. Do not use HTML
or italics for this convention. A rejected agent check is not a planning
response: stop with the required explanation and do not imply planning began.

Use the active team's capabilities proportionally. The master owns conversation,
decisions and the canonical plan. Its explorer can investigate repository facts;
its planner can develop technical options and draft proposals for complex work.
Give those specialists bounded questions and relevant agreed requirements; have
them return findings to the master rather than concurrently editing the plan.
Use the team's verifier for authorized checks when they help validate feasibility.
Do small planning tasks directly. Do not use development specialists to implement
before the user asks. Once implementation is requested, hand the canonical plan
to the team's appropriate developer/quick-fixer and use its reviewer/verifier as
needed. Team specialists involved in drafting never replace the fresh independent
plan reviewers. Do not guess another team's identity.

## Conversation and transitions

Speak in the user's language. Persist all authored content in English: filename,
title, metadata, plan, tracking, decisions, open questions, and review findings.
Preserve code identifiers and required literal product copy in its original language.

The user leads. Listen, suggest useful alternatives, and ask focused questions
only when they clarify the emerging idea. Do not run a questionnaire, force a
template onto brainstorming, or decide requirements on the user's behalf.
Inspect the repository to answer factual questions rather than asking the user
to supply facts you can discover. Distinguish suggestions from agreed decisions.

Phases are `brainstorming`, `draft`, `guided-review`, `independent-review`, and
`ready`. They are navigable states, not mandatory gates. Suggest transitions when
useful, but wait for the user's direction. Explicit requests can go directly to
any phase, including guided review after independent review or after readiness.

- With an idea or no arguments, start brainstorming; use the conversation already
  available rather than asking the user to repeat it. Do not create an empty file.
- With a supplied existing file, read it and enter draft by default. Honor an
  explicit phase request instead. Explain the saved progress and next step;
  preserve its content and existing approvals unless affected by changes.
- Do not silently pick a plan if the target is ambiguous or a supplied path is
  missing. Ask which file to use; do not overwrite unrelated files.
- A user can say the plan is ready at any time, even before a draft exists.
  Save the agreed scope in a concise plan, record skipped reviews and remaining
  uncertainties honestly, set `ready`, and stop planning without another gate.
- A request to implement also finalizes the current plan and authorizes starting
  implementation from it, within the agreed scope and normal access rules.
  Readiness by itself does not authorize implementation. An unresolved choice
  required for implementation must not be invented.

## Draft and durable file

Create new plans in the project's `.plan/` directory, with local creation time:
`YYYY-MM-DD-HH-mm-short_english_title.md` (`mm` means minutes).
Keep the filename stable. On a collision, choose a distinct descriptive title;
never overwrite another plan. If an input file is outside `.plan/`, preserve the
source and create a working copy in `.plan/`, explaining the new canonical path.
Existing plans already in `.plan/` keep their paths. Do not change Git ignore
rules automatically.

Use only a small YAML header and ordinary Markdown, for example:

```markdown
---
status: draft
next: Review scope with the user
---

# Short plan title

## Goal and scope
...

## Proposed behavior and decisions
...

## Implementation
...

## Verification
...

## Review tracking
- [ ] Goal and scope
- [ ] Proposed behavior and decisions
- [ ] Implementation
- [ ] Verification

## Open questions
...
```

Adapt sections to the change; small plans should be short. Include relevant
repository paths, constraints, acceptance criteria, dependencies, and concrete
verification when applicable. Separate agreed decisions from assumptions and
unresolved questions. The document must stand on its own without this chat.
Use valid YAML scalars (quote values containing colon-space or other YAML syntax).

The file is the source of truth. Save agreed changes, phase transitions, review
progress and the next useful action as work proceeds. Keep tracking concise;
do not transcribe the conversation or introduce a separate state database.
Check the current file before editing so external changes are preserved. On
resume, compare saved approvals with current content; ask if an approval's
validity is uncertain rather than assuming it covers changed text.

## Guided review

Review the current file by meaningful sections, one part per turn, in the user's
language. Explain the content and relevant trade-offs, then wait for the user
to indicate understanding and approval or request changes. Answer questions
without treating them as approval. Apply requested changes and re-present the
affected part when needed. Mark a section approved only on explicit approval.

The user may select the whole plan or specific sections at any time. Preserve
unaffected approvals. Invalidate and re-present any previously approved section
materially affected by an edit, including changes arising from independent review.
After finishing the requested review, summarize and ask what the user wants next;
do not launch independent reviewers or implementation automatically.

## Independent review

When requested, launch fresh `team-plan-auditor` and `team-plan-reader` subagents,
in parallel where supported. These are shared reviewers outside the development
teams. Do not reuse sessions that helped draft the plan or substitute the team's
reviewer. Each receives only the canonical plan path, repository root, its review
assignment, and the instruction to read the file and inspect relevant repository
facts. Do not pass the conversation, previous findings, or explanations that
compensate for missing information in the document.

They must be read-only and return findings in English to the master. The auditor
checks feasibility, contradictions, dependencies, risks and verification. The
reader checks ambiguity, missing requirements, unstated assumptions, edge cases
and whether an implementer can act without guessing. Ask for section references,
evidence, impact, and a concrete question or suggested correction per finding.

If fresh independent sessions or these agents are unavailable, explain that
independent review is unavailable in this runtime. Offer guided review or let
the user mark the plan ready; never claim a self-review was independent.

As master, check findings against the file and repository, deduplicate them,
and present actionable issues to the user by topic, in manageable turns. Do not
silently resolve product or scope decisions. Record concise findings and their
disposition (resolved, dismissed with rationale, or deferred) in the plan and
incorporate agreed resolutions. Record failed or skipped reviews accurately.
Do not repeat review automatically: propose another pass only for material new
issues. Offer guided review of changed sections or readiness when finished.

## Ready and handoff

On the user's readiness decision, ensure the file reflects the latest agreements,
set `status: ready` and `next: Implement the plan`, and note any skipped reviews
or unresolved/deferred findings. Report the canonical path concisely. Reviews
may be skipped at the user's direction; do not mark skipped work as completed.
If the user also asked to implement, proceed using that file and the current
team's implementation workflow. Otherwise wait for an implementation request.

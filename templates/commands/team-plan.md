---
# <!-- Managed by named-teams: shared planning -->
description: Build and review a persistent plan through a user-led conversation.
subagent: false
---

Require an active installed team master, verified from its active identity and
instructions, not the arguments. If identity is uncertain or it is not a team
master, stop and ask the user to select one and invoke /team-plan again.
Before planning, successfully load the `team-plan` skill using the skill tool;
if it cannot be loaded, stop and explain. Apply its protocol to: $ARGUMENTS
Do not output or repeat the full protocol.

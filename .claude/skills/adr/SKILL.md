---
description: Create a new Architecture Decision Record (ADR) for this project. Use when the user wants to document an architectural decision, write an ADR, or record a design choice.
allowed-tools: Read, Edit, Write, Bash
---

## ADR creation skill

The current ADR index and next available number:

!`cat docs/adr/README.md`

Today's date: !`date +%Y-%m-%d`

## Instructions

The user wants to create a new ADR. The arguments passed to this skill (if any) describe the decision topic or title.

Work through these steps **in order**, waiting for user confirmation before proceeding to the next:

**Step 1 — Gather context and decision.**
Ask the user for the context (what problem, what forces) and the decision (stated plainly). If the conversation already contains this, summarize it back and confirm before proceeding.

**Step 2 — Alternatives considered.**
Do NOT invent alternatives. Either:
- Extract them from the current conversation if alternatives were discussed, summarize each one and ask the user to confirm or correct, or
- Ask the user directly: "What alternatives did we consider? For each one, give a brief description and why it wasn't chosen."

If no alternatives, suggest alternatives to confirm this is a good decision.

**Step 3 — Consequences.**
Draft suggested bullet points for Positive, Negative/Trade-offs, and Neutral consequences based on the decision and context. Present them to the user and ask for confirmation or corrections before writing anything to disk.

**Step 4 — Write the files.**
Only after steps 1–3 are confirmed:
- Determine the next ADR number (highest NNNN in the index + 1, zero-padded to 4 digits).
- Create `docs/adr/NNNN-kebab-case-title.md` with:
  - Title: a descriptive title for the decision taken
  - Date: today's date from above
  - Deciders: All people involved in decision
  - All confirmed content from steps 1–3
- Add a row to the index table in `docs/adr/README.md` (Status: `Active`).
- Commit both files with message: `docs: add ADR-NNNN <title>`

The ADR is a *record of an accepted decision* — write it as if the decision is already made.

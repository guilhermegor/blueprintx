# <Feature name>

Status: draft
Owner: <name>
Created: YYYY-MM-DD

Copy this file to `.specs/features/<feature-slug>/spec.md` (or
`.specs/features/<feature-slug>.md` for a small feature) and fill it in before
writing code. Delete any section that genuinely does not apply — an empty
heading left in place reads as an unanswered question, not a skip.

## Objective

<One or two sentences: what this feature does and why it matters. Not the
implementation — the outcome.>

## User Stories

One `US-XXX` per distinct user goal, numbered sequentially within this file.

- US-001: As a <role>, I want <capability>, so that <benefit>.
- US-002: As a <role>, I want <capability>, so that <benefit>.

## Acceptance Criteria

One `AC-XXX` per testable behavior, phrased Given/When/Then so each maps
directly to a test case. Note which user story it satisfies.

- AC-001 (US-001): Given <context>, when <action>, then <outcome>.
- AC-002 (US-001): Given <context>, when <action>, then <outcome>.

## Assumptions

Anything taken as given but not verified — a dependency, an environment
detail, a decision made elsewhere. Revisit these if one turns out false.

- ASM-001: <assumption>.

## Open Questions

Anything that blocks or shapes the design and does not yet have an answer.
Resolve before implementation starts, or record the answer inline and move
the question to a "Resolved" subsection instead of deleting it.

- Q-001: <question>.

## Out of Scope

Explicitly excluded behavior — the fastest way to stop scope creep is to name
what this feature deliberately does not do.

- <excluded behavior>.

## Notes

Links to related issues, prior art, or anything else worth keeping with the
spec but that does not fit the sections above.

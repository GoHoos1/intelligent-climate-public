# ADR 0003: Phase 2 Safe Scheduled Control Transition

## Status

Accepted for Phase 2 implementation.

## Context

Release 0.0.8 completed and accepted the Phase 1 observation-only baseline.
Phase 2 introduces safe scheduled control, but the approved implementation
backlog deliberately separates vocabulary, pure policy, shadow evaluation,
frontend control surfaces, and physical command authority.

The Phase 1 invariant cannot simply be deleted at the start of Phase 2. It must
be replaced by dependency-ordered gates that keep premature physical behavior
impossible.

## Decision

The approved
[`phase-2-requirements-and-technical-design.md`](../phase-2-requirements-and-technical-design.md)
is the authoritative Phase 2 design.

Release 0.0.8 remains the immutable migration and behavioral baseline. Its
accepted parent config-entry 1.1 document, zone-data v1 document, options,
runtime Store 1.2/schema v1 document, platform inventory, operating modes, and
acceptance evidence are preserved in a checked fixture and executable tests.

Phase 2 implementation follows the numbered backlog. In particular:

- Tasks 1 through 16 add no active command sink or Home Assistant service call.
- Tasks 17 through 27 may create only suppressed Observe/Shadow behavior.
- Task 28 may introduce the physical adapter only in isolation with fake-service
  tests and an explicit allowlist.
- No live active sink may be constructible until Task 30's authority gates.
- No single-system physical integration occurs before Task 31.
- No public synchronization occurs before private acceptance.

Observe Only remains a permanent zero-command mode. Disabling automation does
not remove sensor visibility, history, diagnostics, or later explicit Manual
Control access.

## Consequences

Each task must update its sentinels only as narrowly as its approved scope
requires. A later task may replace a Task 1 absence assertion with a stronger
structural or behavioral gate, but may not simply remove safety coverage.

The Phase 7 Simulation Lab and Phase 4 psychrometric comfort targeting remain
planned extension points, not Phase 2 runtime behavior.

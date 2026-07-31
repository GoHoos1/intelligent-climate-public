# ADR 0001: Observation-Only Foundation

## Status

Accepted for the repository-foundation task.

## Context

The product specification describes a future climate-control platform with
scheduling, predictive control, thermal learning, equipment intelligence, and
manual override handling. The Phase 1 technical design narrows the first phase
to foundation and observation.

The repository foundation is narrower still. It establishes the package
structure, development tooling, minimal domain terminology, and the safety
boundary before any real observation pipeline or Home Assistant entities exist.

## Decision

The initial foundation is strictly observation-only. It contains no code that
can call Home Assistant services to change thermostats, fans, switches,
humidifiers, dehumidifiers, ventilation systems, or other climate-related
entities.

A command boundary exists now so future decision-producing code has a required
interface for command intent handling. The only implementation in this slice is
`ObserveOnlyCommandSink`, which returns a suppressed result and performs no
external side effects.

Future control code must remain separated from observational code. It must not
be introduced by adding a hidden flag, dormant service-call branch, commented
service call, or alternate implementation inside the observation-only boundary.

## Invariant Protection

The invariant is protected by tests that:

- Exercise `ObserveOnlyCommandSink`.
- Assert that no Home Assistant service call is made through the boundary.
- Run an AST-based repository invariant check over integration Python files for
  direct `.services.async_call` expressions and imported `async_call` helpers
  from service modules.

The source-level guard is a repository invariant check, not mathematical proof
of all possible control behavior. It is paired with design review, behavioral
tests, and the absence of any active command adapter.

## Future Physical Control Review

Before physical control can ever be introduced, the project needs explicit
design review covering:

- The active command adapter and its ownership boundary.
- User-facing enablement and opt-in flow.
- Safety limits and thermostat capability checks.
- Manual override handling and command correlation.
- No-fight behavior with wall thermostats and Home Assistant automations.
- Restart, unload, unavailable-entity, and command-failure behavior.
- Tests proving that active control is impossible unless all safety gates pass.


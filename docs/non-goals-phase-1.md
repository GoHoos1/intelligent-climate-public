# Phase 1 Non-Goals

Phase 1 is observation-only. The repository foundation is even narrower: it
establishes package structure, tooling, minimal terminology, and the command
boundary only.

The following are prohibited in Phase 1 unless a later approved slice explicitly
changes the phase boundary:

- Any physical HVAC command.
- Scheduling.
- Manual override handling.
- Window suspension.
- Occupancy-driven control.
- Fan control.
- Humidity control.
- Predictive control.
- Thermal modeling.
- Simulation.
- Adaptive start or stop.
- Heat-pump optimization.
- Auxiliary-heat logic.
- Shared-equipment command arbitration.
- Advanced frontend work.
- Placeholder entities for future features.

The integration must not create empty or unknown-state entities for future
features. Future capability must be added only when it has real behavior,
documentation, tests, and safety review.


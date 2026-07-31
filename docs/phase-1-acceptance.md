# Phase 1 Acceptance Record

**Release:** 0.0.8  
**Accepted:** 2026-07-29  
**Result:** All 35 Phase 1 acceptance criteria passed

## Scope

This record closes Phase 1: Foundation and Observation. Phase 1 remains
strictly observation-only. It contains no active HVAC command adapter,
predictive control, schedule, manual override, window suspension, occupancy
control, fan control, or simulation runtime.

The acceptance decision combines:

- automated tests and static validation;
- private and public GitHub CI;
- a live Home Assistant OS upgrade and restart smoke test;
- the required configuration UI walkthrough for P1-AC-003; and
- the required Event, Logbook, Latest Activity, diagnostics, and restart
  walkthrough for P1-AC-026.

No private diagnostic download, screenshot, raw entity ID, user-assigned source
name, config-entry ID, device ID, or household-specific value is included in
this repository record.

## Release and automated evidence

- Candidate version: 0.0.8
- Automated tests: 817 passed
- Statement coverage: 97.88%
- Branch coverage: 95.21%
- Combined coverage: 97.29%
- `config_flow.py`: 100% line and branch coverage
- `zone_flow.py`: 100% line and branch coverage
- Mandatory no-physical-control tests: 25 passed
- External network sockets disabled for the full pytest suite
- Ruff lint: passed
- Ruff formatting: passed
- mypy: passed
- JSON validation: passed
- Git patch hygiene: passed

Private release:

- Repository: `GoHoos1/intelligent-climate`
- Release PR:
  [#22](https://github.com/GoHoos1/intelligent-climate/pull/22)
- Merge:
  [`28dcea6c`](https://github.com/GoHoos1/intelligent-climate/commit/28dcea6cf9e52361e4c2fd7e3f39a026a3451f03)
- [Quality](https://github.com/GoHoos1/intelligent-climate/actions/runs/30457676053),
  [Hassfest](https://github.com/GoHoos1/intelligent-climate/actions/runs/30457676079),
  and
  [HACS](https://github.com/GoHoos1/intelligent-climate/actions/runs/30457676467)
  passed on the reviewed candidate.

Public release:

- Repository: `GoHoos1/intelligent-climate-public`
- Release PR:
  [#9](https://github.com/GoHoos1/intelligent-climate-public/pull/9)
- Merge:
  [`cc7adcb7`](https://github.com/GoHoos1/intelligent-climate-public/commit/cc7adcb75991ca834f58e1394dbd330dd104f142)
- [Quality](https://github.com/GoHoos1/intelligent-climate-public/actions/runs/30458096224)
  and
  [Hassfest](https://github.com/GoHoos1/intelligent-climate-public/actions/runs/30458096088)
  passed on the reviewed candidate.

## Live Home Assistant evidence

The live walkthrough used Intelligent Climate 0.0.8 on the validated Home
Assistant OS deployment profile.

### Upgrade and restart baseline

- Home Assistant reported no Intelligent Climate Repair.
- Downloaded diagnostics identified integration version 0.0.8.
- Runtime Store schema 1.2 loaded writable and clean.
- The previous shutdown was recorded as clean.
- Runtime returned to `observing`.
- The configured equipment group, zone, thermostat, and temperature source
  loaded without a degraded zone or excluded source.
- The bounded activity records were unique and chronological.

### P1-AC-003 configuration UI walkthrough

- The existing zone reconfiguration form opened with its saved thermostat and
  temperature-source values prefilled.
- Renaming the zone completed without changing its thermostat or source
  assignment.
- The renamed zone retained its 10 entities, and the integration retained its
  two-device/14-entity baseline.
- A temporary second zone was added through the native integration UI using
  the existing shared parent thermostat and a valid temperature source.
- The temporary zone created the expected 10 entities. The integration
  increased to three devices and 24 entities without creating another
  equipment group.
- Removing only the temporary zone returned the integration exactly to two
  devices and 14 entities.
- The retained zone remained intact, and no orphaned device or Repair appeared.

Result: P1-AC-003 passed.

### P1-AC-026 activity and restart walkthrough

- The zone device exposed its Activity Event entity.
- The Activity Event reported `thermostat_observation_changed`.
- Home Assistant displayed Intelligent Climate activity in the device activity
  timeline, including observation state, thermostat capability, operating
  mode, and valid-source changes.
- The Latest Activity sensor displayed the matching most recent material
  activity.
- After a normal Home Assistant restart, observation resumed automatically.
- The zone returned to `observe_only`, reconciliation completed, one valid
  temperature source was active, and source and thermostat degradation were
  both clear.
- Prior activity remained visible, Latest Activity remained populated, and a
  new thermostat-observation event was recorded during startup.

Result: P1-AC-026 passed.

## Acceptance traceability

| Criterion | Result | Evidence |
|---|---|---|
| P1-AC-001 | Pass | HACS structure, manifest tests, private Quality/Hassfest/HACS, and public Quality/Hassfest passed. |
| P1-AC-002 | Pass | Home Assistant 2026.7.0 minimum declared; 0.0.8 loaded and restarted on the validated HAOS deployment. |
| P1-AC-003 | Pass | Automated parent/subentry flow coverage plus the completed add/reconfigure/remove UI walkthrough. |
| P1-AC-004 | Pass | Single, independent, and shared/zoned graphs are represented, validated, decoded, and exercised. |
| P1-AC-005 | Pass | Duplicate thermostat ownership is rejected during setup and reconfiguration. |
| P1-AC-006 | Pass | Every options branch and per-source metadata reconfiguration branch is tested. |
| P1-AC-007 | Pass | Parent and zone graph changes preserve generated group, zone, and retained-source IDs. |
| P1-AC-008 | Pass | Setup, reload, unload, core-stop cleanup, and multiple-entry isolation are covered. |
| P1-AC-009 | Pass | Config-entry and Store migration and recovery are transactional and tested. |
| P1-AC-010 | Pass | Device identifiers and entity unique IDs use immutable generated IDs and survive renames. |
| P1-AC-011 | Pass | Generic capability discovery and the sanitized Nest fixture prove conservative observability. |
| P1-AC-012 | Pass | Exact applicable Phase 1 entity-inventory snapshots pass. |
| P1-AC-013 | Pass | Conflicting multi-thermostat observations are withheld and marked degraded. |
| P1-AC-014 | Pass | Virtual climate feature mask is zero; setters reject without a service call. |
| P1-AC-015 | Pass | All 25 mandatory no-command tests pass and the command journal remains empty. |
| P1-AC-016 | Pass | Unit conversion, calibration order, aggregation, and display conversion are deterministic. |
| P1-AC-017 | Pass | Mean, median, weighted-average, and priority aggregation are covered. |
| P1-AC-018 | Pass | Every documented source-quality and exclusion reason is covered. |
| P1-AC-019 | Pass | Restored and unconfirmed-jump observations remain excluded. |
| P1-AC-020 | Pass | Minimum-count failure and restart/source-loss paths publish no invented value. |
| P1-AC-021 | Pass | Recovery requires two valid evaluations at least 30 seconds apart; invalid data resets the candidate. |
| P1-AC-022 | Pass | Startup and reload reconciliation remain command-free. |
| P1-AC-023 | Pass | Missing and conflicting thermostat observations degrade safely while original thermostats remain independent. |
| P1-AC-024 | Pass | Store bounds, debounce, writer serialization, and material-only persistence pass. |
| P1-AC-025 | Pass | Missing, corrupt, future, and quarantined Store cases remain fail-safe. |
| P1-AC-026 | Pass | Automated Event/history/diagnostic tests plus the completed Activity Event, Logbook, Latest Activity, diagnostics, and restart walkthrough. |
| P1-AC-027 | Pass | Setup, unload, state, and recovery logs use stable reason codes with warning cooldown coverage. |
| P1-AC-028 | Pass | Diagnostics allowlisting, pseudonymization, and forbidden-data recursion pass. |
| P1-AC-029 | Pass | Entity, migration, Store, command-boundary, and no-zone Repairs lifecycle tests pass. |
| P1-AC-030 | Pass | Event-driven targeted coalescing and single-deadline watchdog behavior pass. |
| P1-AC-031 | Pass | Overall thresholds pass and both config-flow modules have 100% line and branch coverage. |
| P1-AC-032 | Pass | Tests use deterministic clocks and fixtures with external sockets disabled. |
| P1-AC-033 | Pass | Predictive, schedule, model, confidence, simulation, and active-command surfaces remain absent. |
| P1-AC-034 | Pass | User documentation covers observation-only behavior, entities, exclusions, diagnostics, Repairs, reconfiguration, and original-thermostat use. |
| P1-AC-035 | Pass | The sanitized Nest fixture deterministically reports only supported public observations. |

## Closeout decision

P1-AC-001 through P1-AC-035 all pass. Phase 1 is complete and accepted in
release 0.0.8.

Phase 2 may now enter design review. Physical HVAC control remains prohibited
until the Phase 2 design, safety gates, migrations, user controls, and
acceptance criteria are separately approved and implemented.


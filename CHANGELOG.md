# Changelog

This changelog records source changes in the public Intelligent Climate
distribution repository. It does not assert that a public release tag exists.

## Unreleased

No unreleased changes.

## 0.0.5 - 2026-07-28

### Added

- Added strict frozen/slotted activity records with stable UUIDs, aware
  timestamps, bounded scalar detail, stable type/reason/severity vocabularies,
  and privacy-safe explanations.
- Added entry-scoped history pruned by configured age and count with an absolute
  500-record maximum, immutable latest/zone views, deterministic restore, and
  listener cleanup.
- Added one diagnostic Activity Event entity on each equipment-group and zone
  device plus one diagnostic Latest Activity sensor per zone.
- Added one exact `intelligent_climate_activity` event-bus publication for every
  newly accepted record. Event entities provide Recorder/Logbook visibility
  without a duplicate custom Logbook record.
- Added Home Assistant Store version 1 persistence at
  `intelligent_climate.<entry_id>` with atomic writes, 30-second debounce,
  five-minute maximum dirty interval, one writer, bounded retry, Store
  failure/recovery activity, Repairs wiring, and a five-second unload limit.
- Added backward-compatible diagnostics schema version 1 activity history and
  Store-health projections.

### Changed

- Narrowed the unused Store v1 `decisions` array to strict typed activity
  records without renaming the field or changing the Store/inner schema
  version. `command_journal` remains always empty.
- Added semantic materiality for runtime state, source exclusion/recovery,
  thermostat mode/target, capability, Repairs, unsupported-control, Store, and
  lifecycle activity while ignoring revisions, timestamps, and unchanged
  reports alone.
- Bumped integration and package versions from 0.0.4 to 0.0.5 without changing
  config-entry version 1.0, zone data version 1, Store schema version 1, or
  diagnostics schema version 1.

### Security

- Activity, Event attributes, Latest Activity attributes, diagnostics, Repairs,
  and event-bus payloads exclude raw entity IDs, user-assigned names, State
  objects, source values, contexts, credentials, URLs, paths, exception text,
  and command payloads.
- Persisted temperatures and source baselines are saved only for future
  continuity work and are not hydrated into Task 14 coordinator state or public
  entities.
- The integration remains strictly observation-only and adds no physical
  service call, writable climate capability, schedule, prediction, simulation,
  or command adapter.

## 0.0.4 - 2026-07-27

### Added

- Added entry-scoped Home Assistant Repairs issues for `missing_entity`,
  `incompatible_entity`, `migration_failed`, `store_write_failed`, and
  `command_boundary_violation`.
- Added deterministic `entry_<12 lowercase hex>_<issue_code>` issue IDs,
  translated actionable issue text, current-error severity, documented
  persistence, and deterministic creation and clearing behavior.
- Added a typed Store-write failure hook that reports the issue after three
  consecutive failures and clears it after a successful/reset notification.
  Runtime Store loading and writing remain unimplemented.
- Added sorted active issue codes to the bounded diagnostics runtime projection
  without changing diagnostics schema version 1.

### Changed

- Corrected the diagnostics privacy documentation to distinguish the
  Intelligent Climate-owned data section from Home Assistant's outer diagnostic
  envelope and filename.
- Documented that report-scoped entity/name pseudonyms change between downloads
  while integration-generated equipment-group, zone, and source UUIDs remain
  stable and can correlate reports from the same configuration.
- Bumped integration and package versions from 0.0.3 to 0.0.4 without changing
  config-entry, zone, Store-model, or diagnostics schema versions.

### Security

- Unexpected nonempty command intents remain suppressed without a Home
  Assistant service call or physical command and now create a payload-free
  persistent Repairs issue.
- Repairs adds no automatic repair flow, configuration mutation, Store
  filesystem behavior, or writable/physical HVAC behavior.

## 0.0.3 - 2026-07-25

### Added

- Added Home Assistant config-entry diagnostics through
  `async_get_config_entry_diagnostics`.
- Added diagnostics schema version 1 with integration/config versions,
  configuration lifecycle state, equipment and zone structure, safe observation
  options, thermostat capabilities and observed state, zone aggregation
  health, and configured-order source-quality summaries.
- Added loaded, unloaded, awaiting-first-zone, transitional-skeleton,
  disabled-observation, missing-source, stale, restored, implausible,
  jump-rejected, contradictory, outlier, and malformed-configuration coverage.

### Changed

- Rewrote the README around installation, configuration, zone behavior,
  diagnostics, troubleshooting, privacy, and current limitations for integration
  users.
- Added a concise recent-changes section near the top of the README.
- Reorganized the full historical changelog into versioned releases.
- Bumped integration and package versions from 0.0.2 to 0.0.3 without changing
  config-entry or zone schema versions.

### Fixed

- Invalid or unloaded entries now return bounded diagnostic lifecycle and decode
  status instead of exposing malformed persisted values or requiring runtime
  data.
- Diagnostic source rows use final aggregation quality, so outlier and
  contradiction results are represented accurately.

### Security

- Added a strict typed allowlist projection; raw config-entry dictionaries,
  subentry dictionaries, Home Assistant `State` objects, and arbitrary
  attributes are never copied into diagnostics.
- Added report-scoped HMAC-SHA256 pseudonyms for every entity reference and
  user-assigned name. Every report receives a fresh random secret salt that is
  never returned, preventing ordinary cross-report correlation of those
  references. Integration-generated equipment-group, zone, and source UUIDs
  remain stable and may correlate reports from the same configuration.
- Added recursive forbidden-value tests covering entry/entity/name/device/area/
  context/user/account identifiers, credentials, URLs, coordinates, addresses,
  private keys, environment/path-like data, and arbitrary provider attributes.
- Confirmed diagnostic generation performs no network or filesystem I/O,
  polling, service call, reload, listener/timer registration, or runtime
  mutation.

## 0.0.2 - 2026-07-24

### Fixed

- Corrected startup entity ordering so a structurally valid persisted thermostat
  or temperature source no longer fails setup solely because its owning
  integration has not loaded yet.
- Kept the zone entity unavailable while required live data is absent, then
  recovered it automatically from state-change or state-report events when the
  entities appeared.

### Changed

- Separated strict interactive entity selection from persisted startup
  validation. Interactive selections still require current entities, supported
  domains, and the temperature sensor device class.
- Persisted setup now validates entity-ID structure, binding kind, stable source
  identity, parent/zone relationships, and exclusive thermostat ownership
  without requiring a current Home Assistant state.
- Preserved observation-only behavior: the recovery path adds no polling,
  reload, service call, command, or physical control.

## 0.0.1 - 2026-07-24

### Fixed

- Corrected the first-zone creation lifecycle race by scheduling exactly one
  parent reload after Home Assistant commits the new zone subentry.
- Changed source freshness from `State.last_updated` to
  `State.last_reported`, so recently reported unchanged readings remain fresh.

### Added

- Added state-report subscriptions alongside state-change subscriptions.
  Unchanged reports now use the same coalesced affected-zone reevaluation path.
- Added automatic first-zone and unchanged-report recovery tests while
  preserving the existing no-physical-control and read-only climate invariants.

## 0.0.0 - 2026-07-23

### Added

- Established the public source-available repository under the PolyForm Strict
  License 1.0.0, Home Assistant custom integration package, HACS metadata,
  Python 3.14 tooling, Quality/Hassfest/HACS workflows, strict typing, and the
  observation-only architecture decision.
- Added immutable UUID-backed equipment-group, zone, and source identifiers,
  strict schema decoders/encoders, options and future runtime Store models, and
  migration scaffolding. No Store read/write path was implemented.
- Added the UI equipment-group flow, native zone config subentries, stable zone
  add/rename/reconfigure lifecycle, and strict graph validation.
- Added one exclusively owned existing climate thermostat per equipment group
  and one or more climate-current-temperature or temperature-sensor sources per
  zone. Retained sources preserve their identity and metadata during zone
  reconfiguration.
- Added public-state thermostat capability discovery with complete, partial, and
  unavailable results. HVAC stage and auxiliary heat remain explicitly not
  observable through the generic contract.
- Added pure source normalization for Celsius/Fahrenheit temperature and
  humidity percentage points, calibration, and stable unavailable/unknown/
  nonnumeric/nonfinite/unsupported-unit reason codes.
- Added pure freshness and health evaluation for plausible bounds,
  `last_reported` age, restored values, immutable accepted baselines, and
  confirmed temperature jumps.
- Added deterministic mean, median, weighted-average, and priority aggregation;
  temperature MAD outlier rejection; two-source contradiction handling;
  minimum-valid-source enforcement; and configured-order source accounting.
- Added the entry-scoped, event-driven observe-only coordinator with immutable
  snapshots, targeted reevaluation, burst coalescing, reconciliation, freshness
  deadlines, and unload/reload cleanup.
- Added exactly one read-only virtual climate entity per configured zone with a
  stable zone-based unique ID, integration-owned group/zone devices, effective
  temperature and optional humidity, and unambiguous observed mode/action/target
  presentation.
- Added translated rejection for every supported virtual-climate setter and
  source/behavior tests that guard against Home Assistant service-call paths.

### Detailed development history

- **Foundation and schemas (Tasks 1-2):** package structure, identifiers,
  operating-mode terminology, command sink, schema boundaries, options, future
  Store document types, tests, CI, and repository documentation.
- **Configuration and identity (Tasks 3-5):** equipment-group UI setup, native
  zone subentries, stable IDs, entity selection, exclusive thermostat ownership,
  source validation, and retained-source reconfiguration.
- **Observation algorithms (Tasks 6-9):** thermostat capabilities, source
  normalization, freshness/health, jump confirmation, outlier/contradiction
  handling, and temperature/humidity aggregation.
- **Runtime and entity surface (Tasks 10-11):** event-driven coordinator,
  reconciliation and freshness scheduling, startup/unload cleanup, and one
  read-only zone climate entity.

The 0.0.0 foundation added no diagnostics, Repairs, runtime Store persistence,
activity history/events, schedule, predictive control, physical command
adapter, service call, or writable HVAC behavior.

This public distribution remains source-available under the PolyForm Strict
License 1.0.0. See `LICENSE` and `NOTICE`.

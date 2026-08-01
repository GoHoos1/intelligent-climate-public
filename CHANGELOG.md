# Changelog

This changelog records source changes in the public Intelligent Climate source
distribution repository. It does not assert that a public release tag exists.

## Unreleased

No unreleased changes.

## 0.0.13 - 2026-08-01

### Fixed

- Corrected the Today chart's browser SVG namespace so dynamic grid lines,
  labels, paths, sample markers, cursor, and annotations render as real SVG
  elements in Chrome, Safari, and other standards-compliant browsers.
- Added a visible early-history window that expands toward the full Today view
  as observations accumulate, including flat two-sample and nearly flat
  three-sample traces five minutes apart.
- Clarified that Shadow qualification has not started while Scheduled Shadow is
  inactive, without implying that ordinary observation history is missing.

### Security

- The correctness release preserves existing configuration and stored
  observations and remains read-only. It adds no physical adapter, Home
  Assistant service call, writable climate behavior, predictive control, or
  control authority.

## 0.0.12 - 2026-07-31

### Fixed

- Hardened the Today temperature chart for flat or nearly flat traces with an
  explicit high-contrast line, visible sample markers, and geometry assertions
  that verify more than SVG element presence.
- Reduced the chart height on tablet and mobile displays without changing
  stored presentation history.

### Security

- The graph-rendering release remains read-only and adds no physical adapter,
  Home Assistant service call, writable climate behavior, or control authority.

## 0.0.11 - 2026-07-31

### Fixed

- Corrected thermostat-state interpretation so HVAC operation comes from the
  thermostat's reported `hvac_action`, while `fan_mode` represents only
  explicit fan-only circulation.
- Distinguished unavailable, not-reported, and older unknown observations,
  and added a clearly labeled derived air-handler status during active heating
  or cooling without claiming direct blower telemetry.
- Repaired the Today chart with one labeled temperature scale, consistent
  Fahrenheit/Celsius rendering, visible indoor and target lines, sample-count
  progress, latest-sample time and source, and live detail refreshes.
- Relabeled optional HVAC-stage inputs as external equipment-stage evidence and
  collapsed repetitive equipment-state samples into meaningful transitions.

### Security

- The correctness release remains read-only and adds no physical adapter, Home
  Assistant service call, writable climate behavior, or control authority.

## 0.0.10 - 2026-07-31

### Changed

- Added zone reconfiguration selectors for humidity, window/door contacts,
  occupancy, HVAC stages, and fans. Thermostat `current_humidity` is supported
  as a humidity source, and explicitly selected optional sources become
  reviewed and enabled without changing stable source or zone identities.
- Added a sidebar display preference that follows Home Assistant by default or
  can force Fahrenheit or Celsius consistently across values, explanations,
  and the Today timeline.
- Changed Activity to newest-first by default with bounded older-page loading,
  while preserving canonical chronological storage.
- Distinguished active Repairs from retained historical activity and replaced
  sparse Today charts with a compact collecting-history state.
- Reworked preview-oriented descriptions into user-focused status and settings
  language. Existing migrated configuration entries remain valid.

### Security

- The stabilization remains read-only and adds no physical adapter, Home
  Assistant service call, writable climate behavior, or Scheduled Control
  authority.

## 0.0.9 - 2026-07-31

### Phase 2 development

- Began Phase 2 Task 1 without changing runtime behavior or the 0.0.8 package
  version.
- Added immutable 0.0.8 config, zone, options, Store, platform, operating-mode,
  and acceptance-evidence fixtures for future migration testing.
- Added sentinels that reject Phase 2 runtime vocabulary, frontend surfaces,
  physical adapters, and Home Assistant service calls before their approved
  backlog tasks.
- Added the approved Phase 2 requirements/design and governing source documents
  to the development repository.
- Added Task 2's typed schedule, override, decision, command, safety, contact,
  and occupancy identifiers plus operating-mode, execution-state, reason-code,
  and live/simulation context vocabulary without runtime wiring.
- Added Task 3's immutable weekly schedule models, strict JSON codec, canonical
  ordering, and complete identity/timezone/zone/capability/limit validation
  without persistence, evaluation, runtime wiring, or command behavior.
- Added Task 4's pure circular weekly schedule evaluator with inherited-period,
  next-boundary, and next-material-target calculation plus deterministic
  local-wall-time resolution, without timers, persistence, runtime wiring, or
  command behavior.
- Added Task 5's deterministic clock matrix covering spring gaps, fall folds,
  midnight, empty days, Sunday/Monday wrapping, leap day, non-hour DST,
  no-DST zones, and schedule time-zone changes without runtime behavior.
- Added Task 6's authoritative Schedule Store v1 with verified atomic writes,
  optimistic revision conflicts, canonical post-save publication, semantic
  quarantine, and read-only future-version preservation without runtime wiring.
- Added Task 7's pure config 2.0, zone 2, Runtime Store 2.0/inner 2 target
  schemas, safe 0.0.8 migration dry run, and isolated bounded Presentation
  Trace Store v1 schema without activating migration or runtime control.
- Added Task 8's crash-safe 0.0.8-to-Phase-2 migration transaction, interrupted
  migration reconciliation, verified Runtime Store v2 replacement, bounded
  quarantine and future-version preservation, and post-reconciliation empty
  Presentation Trace initialization. Every migrated and newly configured entry
  remains unarmed in Observe Only, with no Home Assistant service-call path.
- Added Task 9's pure control-precedence resolver, legal-transition state
  machine, explicit Manual Control user-intent authority gate, fail-closed
  recovery discipline, and permanent observation behavior without runtime
  wiring, timers, command plans, or Home Assistant service calls.
- Added Task 10's typed manual-override record and strict codec, complete
  deterministic expiration-policy calculators, privacy-safe projections, and
  immutable cancellation/extension lifecycle without runtime wiring, timers,
  schedule execution, persistence activation, or physical control.
- Added Task 11's typed bounded command journal, strict restart codec,
  stable command/correlation identities, semantic acknowledgement matching,
  and fail-closed external/ambiguous change classification without an adapter,
  sink, dispatch path, runtime wiring, retry execution, or physical control.
- Added Task 12's strict contact-binding codec and deterministic contact
  debounce/grace/minimum-open/close/resume state machine, including unavailable
  fail-closed and privacy-bounded reasons, without subscriptions, timers,
  coordinator wiring, command plans, or physical control.
- Added Task 13's strict occupancy policy codec, stable occupancy-source IDs,
  bounded per-zone effects, and deterministic manual/priority/delay/unavailable
  resolver without runtime source reads, timers, configuration-flow wiring,
  schedule execution, command plans, or physical control.
- Added Task 14's pure shared-equipment safety arbitration, including explicit
  single-authority review, complete zone priority, compatible/opposite demand,
  active-direction preservation, emergency precedence, and uncertain related
  thermostat holds without runtime wiring, a command plan, or physical control.
- Added Task 15's strict fan policy/binding codec, calculated Magnus dew point,
  spread hysteresis, occupancy/HVAC/quiet-time gates, humidity and post-cooling
  lockouts, minimum-on and rolling-hour runtime budget, and correlated
  thermostat fan-mode restore eligibility as pure, unwired fan-only policy.
- Added Task 16's pure central SafetyGate with strict ownership, capability,
  revision/precondition, absolute-limit, deadband, interval, cooldown,
  arbitration, fan-evidence, and authority checks. Its privacy-bounded result
  grants no dispatch authority and remains unwired from the coordinator,
  command plans, sinks, adapters, and Home Assistant service calls.
- Added Task 17's strict typed `CommandPlan`, canonical semantic dedupe, explicit
  manual/scheduled user-context rules, injected input/UTC-clock/sink protocols,
  and typed Observe Only suppression while retaining the Phase 1 runtime probe
  until Task 19. No adapter, service call, or coordinator plan wiring exists.
- Added Task 18's physically inert Shadow sink, privacy-bounded exact
  would-command history with strict Runtime Store-compatible codec, continuous
  24-hour/20-decision/two-transition/95% qualification calculations, current
  blocking-fault handling, and canonical readiness entity snapshots. Runtime
  coordinator/entity wiring and every physical action remain absent.
- Added Task 19's coordinator-owned suppressed-policy composition through
  schedule, override, shared-equipment arbitration, the central SafetyGate,
  and the Shadow sink, plus a bounded 48-hour nonauthoritative Presentation
  Trace Store. Observe Only and Scheduled Shadow remain zero-command modes.
- Added Task 20's versioned backend WebSocket read/subscribe, schedule
  validation/preview/save, activity, Shadow/observation status, DST-correct
  Today timeline, deterministic fact-bounded narrative, and typed manual-action
  contracts without frontend code, active adapters, or Home Assistant service
  calls.
- Added Task 21's strict TypeScript/Lit frontend foundation with versioned
  WebSocket DTO validation, Home Assistant theme tokens, responsive and
  reduced-motion primitives, explicit unavailable-state semantics, and
  automated accessibility checks.
- Added Task 22's bundled Intelligent Climate sidebar with Overview, Sensors,
  Activity, Settings, Shadow readiness, factual status explanations, and a
  DST-correct Today timeline. The panel remains read-only and exposes no
  physical-control action or Home Assistant service-call path.

### Phase 1 documentation

- Recorded the completed Home Assistant 0.0.8 UI, activity, diagnostics, and
  restart walkthrough and formally closed all 35 Phase 1 acceptance criteria.
- Added the Phase 1 acceptance record and updated release, roadmap, design, and
  backlog status from acceptance candidate to accepted.

## 0.0.8 - 2026-07-29

### Added

- Added atomic equipment-group and first-zone setup, parent reconfiguration,
  complete zone/source reconfiguration, and the full safe options flow.
- Added independent and shared/zoned multi-thermostat graphs with explicit zone
  membership and conflict-safe observed state.
- Added the exact Phase 1 sensor, binary-sensor, switch, climate, and Event
  entity matrix.
- Added a sanitized deterministic Nest fixture, full flow-family branch
  coverage, and explicit network isolation for the complete test suite.

### Changed

- Degraded runtime state now requires two valid evaluations separated by at
  least 30 seconds before returning to observing.
- Lifecycle, state-transition, failure, and recovery logs use stable reason
  codes with bounded warning repetition.
- Native zone removal reconciles thermostat membership and shared-zone
  priority without changing stable equipment, zone, or retained-source IDs.

### Security

- The new observation switch changes configuration and reloads the integration
  only; it cannot call or alter physical climate equipment.
- Multi-thermostat disagreement degrades the virtual observation instead of
  inventing a shared mode, action, or target.
- Phase 1 remains network-isolated and strictly observation-only.

## 0.0.7 - 2026-07-28

### Fixed

- Registered one awaited, entry-scoped Home Assistant shutdown job so a normal
  full-core restart persists `last_clean_shutdown: true` before integrations
  and background tasks stop.
- Made the bounded final-save path idempotent, so concurrent or repeated core
  shutdown and integration-unload calls share one verified persistence attempt.
- Released coordinator subscriptions, debounce callbacks, reconciliation
  deadlines, watchdog deadlines, and Store tasks during full-core shutdown.

### Security

- A normal Home Assistant restart is no longer falsely reported as an unclean
  shutdown. The correction changes no entity, schema, event payload, writable
  capability, or physical-command boundary.

## 0.0.6 - 2026-07-28

### Added

- Added transactional config-entry migration from version 1.0 to 1.1. The
  complete parent/options/zone graph is validated before one parent update;
  invalid graphs remain unchanged and create the existing migration Repair.
- Added a canonical Home Assistant Store envelope migration from 1.1 to 1.2
  while preserving Store major version 1, inner schema version 1, the
  `decisions` field, and an always-empty `command_journal`.
- Added bounded Store recovery states for missing, loaded, migrated,
  quarantined, unsupported, and load-failed data, with redacted diagnostics and
  lifecycle activity for migration and unclean prior shutdown.

### Changed

- Validated source baselines now seed restart comparison logic only. Persisted
  zone temperatures remain nonauthoritative and are never published as live
  climate state.
- Semantically invalid Store data is retained in one entry-scoped quarantine
  and replaced only by a later successful clean save. Future or unreadable
  Store envelopes are preserved read-only instead of being downgraded.
- Hardened setup, reconciliation, reload, failed platform unload, clean unload,
  and restart cleanup without changing the Phase 1 entity inventory.
- Bumped integration and package versions from 0.0.5 to 0.0.6 and config-entry
  minor version from 1.0 to 1.1. Zone data version 1, Store major/inner schema
  version 1, and diagnostics schema version 1 remain unchanged.

### Security

- Invalid, foreign-identity, or future-baseline Store data cannot seed runtime
  comparison state. Quarantined payloads are never copied into diagnostics,
  activity, Repairs, or public entities.
- Missing, corrupt, future, or failed persistence never queues a command or
  blocks safe live observation startup.
- The integration remains strictly observation-only and adds no physical
  service call, writable climate capability, schedule, prediction, simulation,
  or command adapter.

## 0.0.5 - 2026-07-27

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

## 0.0.4 - 2026-07-26

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

## 0.0.3 - 2026-07-24

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

- Established the proprietary private repository, Home Assistant custom
  integration package, HACS metadata, Python 3.14 tooling, Quality/Hassfest/HACS
  workflows, strict typing, and the observation-only architecture decision.
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

This public source distribution is licensed under the PolyForm Strict License
1.0.0. See `LICENSE` and `NOTICE`.

# Changelog

## Unreleased

- Added the Phase 1 Task 11 read-only `climate` platform and exactly one
  coordinator-backed virtual climate entity per configured non-skeleton zone.
  Entities follow configured zone order, do not poll or subscribe directly,
  and update through the existing coordinator listener path.
- Added stable `<zone_id>:zone` unique IDs, primary-entity naming, exact zone
  config-subentry association, a stable Intelligent Climate equipment-group
  device, and one child zone device per entity. Zone devices use the
  equipment-group device as `via_device`; physical thermostat and source-sensor
  devices remain untouched.
- Added strict zone availability requiring a successful coordinator, a current
  zone snapshot, completed reconciliation, enabled observation, a current
  effective temperature, and at least one available bound thermostat. Degraded
  aggregation remains available when it produces a value, and missing current
  values never reuse stale observations.
- Added Celsius-source current temperature with tenths precision, optional
  effective humidity, common observed HVAC mode/action, and deterministic
  single-target or target-range consensus only when every bound thermostat is
  available and agrees within an inclusive 0.1°C span.
- Kept `supported_features` exactly `ClimateEntityFeature(0)`. Home Assistant
  2026.7.3 suppresses normal target serialization without target feature bits,
  so Task 11 publishes only one bounded, display-unit-converted set of standard
  observed target attributes through entity extra attributes. It never enables
  writable target, humidity, fan, preset, swing, turn-on, or turn-off features.
- Added translated observation-only `ServiceValidationError` rejection for
  every asynchronous climate mutation method supported by Home Assistant
  2026.7.3, including mode, temperature, humidity, fan, preset, both swing
  setters, turn on/off, and toggle. No setter uses an executor fallback,
  coordinator mutation, service call, command sink, history, or physical
  control.
- Forwarded and unloaded only `Platform.CLIMATE`. Setup now starts the
  coordinator, stores typed runtime data, awaits platform setup, and shuts the
  coordinator down if forwarding fails. Unload keeps the coordinator alive when
  platform unload fails and shuts it down only after successful platform
  removal.
- Added genuine Home Assistant state-machine, entity-registry, device-registry,
  config-entry, config-subentry, service, reload, unload, Celsius, and
  Fahrenheit coverage plus focused consensus, setter, lifecycle, and
  observation-only source scans.
- Confirmed Task 11 adds no sensor, binary-sensor, switch, event, placeholder,
  diagnostics, Repairs, Store, persistence, activity-history, schedule,
  prediction, decision, command, or physical-control surface. The integration
  is now suitable for an initial real Home Assistant installation to verify
  live zone discovery and calculated observations.
- Added the Phase 1 Task 10 entry-scoped observe-only coordinator as typed
  `ConfigEntry.runtime_data`, replacing the temporary untyped per-entry
  `hass.data` placeholder.
- Added immutable runtime configuration, normalized public thermostat state,
  thermostat capability/state wrappers, zone observations, entry snapshots,
  and exact monotonic snapshot revision semantics.
- Added one indexed subscription for the unique union of enabled observation
  sources and configured thermostats, deterministic source/thermostat
  dependency indexes, 100 ms state-burst coalescing, changed-thermostat
  capability refresh, and reevaluation of only affected zones while retaining
  unaffected zone objects and timestamps.
- Wired the existing Task 6-9 capability, normalization, health, jump,
  outlier/contradiction, minimum-count, and aggregation boundaries into the
  live coordinator without duplicating their algorithms.
- Added startup reconciliation and a single earliest-deadline source freshness
  watchdog with a one-microsecond strict-boundary increment. Restored source
  values remain excluded until a non-restored state update.
- Added disabled-observation and transitional-empty-skeleton snapshots that
  install no live subscriptions or timers, plus idempotent unload/reload
  cleanup of subscriptions, debounce, reconciliation, watchdog, and private
  baselines/pending candidates.
- Confirmed Task 10 creates no platforms, devices, entities, services, Store
  reads/writes, persistence, diagnostics, Repairs, history/activity events,
  decision-engine calls, command-sink calls, or physical-control paths. Live
  data remains internal until the Task 11 read-only entity surface.
- Added Phase 1 Task 9 immutable aggregation statuses, reason codes, and results
  with deterministic configured-order reporting of valid, contributing,
  fallback, and excluded sources.
- Added one-pass temperature MAD filtering using
  `max(outlier_floor_c, 3 × 1.4826 × MAD)`, the configured floor when MAD is
  zero, and strict rejection beyond the inclusive threshold.
- Added two-temperature-source contradiction handling beyond twice the outlier
  floor. Both sources remain contradictory; a degraded fallback is available
  only from a unique smallest positive priority when the minimum count permits
  one source. Priority zero is unconfigured and tied best priorities are
  ambiguous.
- Added post-filter minimum-valid-source enforcement plus stable mean, median,
  normalized weighted-average, and explicit-priority aggregation. Successful
  temperatures use Python's one-decimal `round` after calculation without
  rounding source values or spread.
- Added humidity aggregation with existing health exclusions and all four
  strategies, deliberately without temperature MAD, contradiction thresholds,
  or temperature-style rounding.
- Confirmed Task 9 is a pure caller-invoked boundary with no Home Assistant
  state lookup, runtime subscription, coordinator, snapshot, Store access,
  persistence, options flow, entity/device surface, diagnostics, Repairs,
  service call, command decision, or physical control. Task 10 runtime wiring
  remains absent.
- Added Phase 1 Task 8 immutable source-health results and pending temperature
  jump candidates, plus pure health evaluation over caller-supplied Task 7
  observations, timestamps, accepted baselines, and pending state.
- Added inclusive configured temperature plausibility bounds, a fixed inclusive
  humidity range of 0–100 percentage points, restored-value rejection until a
  later non-restored live observation, and freshness rejection only when source
  age strictly exceeds the configured threshold.
- Added temperature rate-of-change evaluation against the last accepted source
  update time. Excessive changes require a second consistent reading at least
  30 seconds later; returning to the accepted range recovers immediately, and a
  different suspicious range restarts confirmation without changing the
  accepted baseline.
- Added deterministic validation and recovery coverage for all Task 7 and Task
  8 exclusions. Task 8 reads no clock, never reuses a rejected source's previous
  value as its current value, and adds no Task 9 outlier/aggregation behavior or
  Task 10 runtime wiring.
- Confirmed Task 8 adds no subscriptions, timers, coordinator, Store access,
  persistence, options flow, entities, devices, diagnostics, Repairs, command
  decisions, service calls, or physical control.
- Added Phase 1 Task 7 immutable source-observation records, the complete
  approved source-quality and exclusion-reason vocabularies, and pure
  temperature and humidity normalizers over supplied public Home Assistant
  `State` objects.
- Added strict numeric parsing, Celsius conversion through Home Assistant's
  `TemperatureConverter`, humidity percentage-point validation, calibration
  after unit conversion, exact raw-value retention, and restored-marker
  recording without Task 8 restored-value rejection.
- Added deterministic exclusions for missing, unknown, unavailable,
  nonnumeric, nonfinite, and unsupported-unit values. Home Assistant 2026.7.3
  serializes climate `current_temperature` values into its configured
  temperature unit without generically publishing that unit on the climate
  `State`. The pure normalizer therefore accepts explicit climate unit context
  from a future caller and fails closed when it is missing or invalid, while
  normal temperature sensors continue to use their own `unit_of_measurement`.
- Confirmed Task 7 adds no subscriptions, freshness or health evaluation,
  outlier rejection, aggregation, coordinator, entities, persistence,
  diagnostics, Repairs, command decisions, services, or physical control.
- Added Phase 1 Task 6 immutable thermostat capability models and pure discovery
  from public Home Assistant climate state and feature attributes.
- Added complete, partial, and unavailable discovery status; conservative
  handling for malformed data and future feature bits; deterministic HVAC,
  fan, and preset mode normalization; and independent target and target-range
  flags when both are advertised.
- Confirmed Home Assistant 2026.7.3 exposes no generic public climate attribute
  for HVAC stage or auxiliary-heat state, so both remain not observable and
  vendor-specific attributes never influence the result.
- Confirmed Task 6 adds no capability refresh wiring, subscriptions,
  coordinator, registry mutation, persistence, entities, command decisions,
  services, or physical control.
- Added Phase 1 Task 5 entity selection and backend validation for one existing
  climate thermostat per equipment group and one or more climate or
  temperature-sensor sources per zone.
- Added exclusive cross-entry thermostat ownership checks, source domain and
  device-class checks, entity-existence checks that accept unknown or
  unavailable states, and fail-closed setup validation.
- Added zone source reconfiguration that preserves retained source IDs and
  metadata, creates IDs only for validated new bindings, removes deselected
  bindings, and avoids reloads for unchanged persisted data.
- Preserved narrow Task 4 compatibility for completely empty binding skeletons;
  partially bound legacy documents are rejected and pre-alpha skeleton parents
  must be removed and recreated because parent reconfiguration remains out of
  scope.
- Confirmed Task 5 adds no source observation, normalization, subscriptions,
  registry mutation, aggregation, coordinator, devices, entities, Store,
  services, or physical control.
- Added the initial repository foundation for the future `intelligent_climate`
  Home Assistant custom integration.
- Added a minimal integration package skeleton with config-entry setup and
  unload lifecycle functions.
- Added minimal typed identifiers, operating-mode terminology, and schema
  version constant.
- Added immutable Phase 1 schema models, JSON encode/decode helpers, strict
  validation, and migration scaffolding for equipment groups, zones,
  observation sources, options, and runtime Store documents.
- Added the Phase 1 basic UI config flow for creating a skeleton equipment
  group from a display name and equipment type, with a generated UUID and
  schema-encoded config-entry data.
- Added native Home Assistant zone config subentries, stable zone UUIDv4
  identity, chained first-zone creation, add/rename flows, per-parent duplicate
  name checks, and fail-closed setup/reload validation.
- Allowed standalone pre-binding zone skeletons to use empty thermostat and
  source collections while retaining all complete-graph thermostat membership,
  temperature-source, ownership, and duplicate-ID safety rules.
- Confirmed the Task 4 scope adds no thermostat/source selection, entity
  validation, devices, entities, coordinator, Store, options flow, parent
  reconfiguration, aggregation, service calls, or physical control.
- Allowed standalone equipment-group documents to represent the pre-thermostat
  skeleton while retaining thermostat requirements for complete configuration
  graphs.
- Added complete English custom-integration config-flow and selector
  translations in `translations/en.json` and removed the unsupported custom
  component `strings.json` translation source.
- Added an observation-only command boundary and tests guarding against Home
  Assistant service-call paths.
- Added HACS metadata, GitHub Actions workflow definitions, development docs,
  non-goals, licensing options, an ADR, and a Phase 1 implementation backlog.

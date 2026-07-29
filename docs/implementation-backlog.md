# Implementation Backlog

This backlog divides the Phase 1 design into small ordered tasks. Every Phase 1
task remains observation-only.

## 1. Repository Foundation

Purpose: Establish the custom-integration package, tooling, documentation, and
command-boundary invariant.

Included scope: Skeleton package, manifest, HACS metadata, minimal typed
identifiers, disabled/observe-only operating mode, command sink, tests, CI, and
repository docs.

Explicit exclusions: Config flow, entities, subscriptions, diagnostics, Repairs,
Store, coordinator, sensor handling, and physical control.

Dependencies: Authoritative docs and owner decisions for the foundation scope.

Acceptance criteria: Package imports, setup/unload tests pass, no service-call
path exists, HACS structure has exactly one integration, docs make current
limitations clear.

Required tests: Import/setup/unload, manifest, identifiers, operating mode,
command sink, no-control path scan.

Safety impact: Establishes the no-physical-control boundary.

Observation-only: Yes.

## Public HACS Release Prerequisite: Original Brand Assets

Purpose: Complete HACS brand requirements with original project assets before
public release.

Included scope: Design original brand assets, add the required integration icon,
remove the temporary HACS `brands` ignore, and validate the final assets before
public HACS release.

Explicit exclusions: Placeholder logos, copied assets from another project, and
AI-generated temporary branding.

Dependencies: Owner-approved final product icon design.

Acceptance criteria: `custom_components/intelligent_climate/brand/icon.png`
contains the final original integration icon, the HACS workflow no longer
ignores `brands`, and HACS validation passes without the brand exception.

Safety impact: None.

Observation-only: Yes.

## 2. Core Configuration and Storage Schemas

Purpose: Define typed schemas for future equipment, zone, source, options, and
runtime Store documents without wiring them into Home Assistant flows.

Included scope: Immutable schema models, version constants, JSON decode/encode
helpers, semantic validation, and migration scaffolding tests.

Explicit exclusions: Config flow UI, subentries, entity selection, persistence
writes, and runtime coordinator.

Dependencies: Repository foundation.

Acceptance criteria: Invalid schema data is rejected with precise errors; valid
minimal one-group/one-zone data round-trips.

Required tests: Schema validation, version handling, invalid identifiers,
duplicate source IDs, and migration failure behavior.

Safety impact: Prevents unsafe or ambiguous config from reaching runtime code.

Observation-only: Yes.

Status: Implemented. This task added schema models, JSON boundary helpers,
strict semantic validation, current-version migration scaffolding, and tests
only. It did not add config flows, options flows, config subentries,
persistence writes, runtime coordination, entities, or physical control.

## 3. Basic Config Flow for One Equipment Group

Purpose: Add the smallest UI flow that creates one physical HVAC equipment-group
entry without zones or thermostat control.

Included scope: `config_flow.py`, translations, one-entry creation, title, basic
equipment-group name/type fields if supported by current schema.

Explicit exclusions: Options flow, reconfigure flow, subentries,
multi-thermostat grouping, source selection, and entities.

Dependencies: Core configuration schemas.

Acceptance criteria: User can create and remove a skeleton config entry through
the UI; no platforms are forwarded.

Required tests: Complete flow, cancellation, duplicate policy if applicable, and
setup/unload after entry creation.

Safety impact: Introduces UI setup without equipment interaction.

Observation-only: Yes.

Status: Implemented. This task added one `user` config-flow step for an
equipment-group display name and equipment type, generated a stable group UUID,
and stored the schema-encoded standalone parent skeleton in config-entry data.
It added no thermostat selection, zones, options, reconfiguration, subentries,
platforms, persistence, coordinator behavior, entities, or physical control.

## 4. Zone Creation and Stable Identifiers

Purpose: Add first-zone modeling and stable ID creation.

Included scope: Zone config document, stable zone ID, basic zone name, and
validation that one zone belongs to one equipment group.

Explicit exclusions: Config subentries until their supported API is verified,
sensor aggregation, thermostat binding, and entities.

Dependencies: Basic config flow.

Acceptance criteria: Zone identity remains stable across reload and rename.

Required tests: Zone schema, ID stability, invalid zone data, reload behavior.

Safety impact: Establishes stable ownership without control.

Observation-only: Yes.

Status: Implemented. This task added native zone config subentries, stable zone
UUIDs, basic add/rename flows, and parent setup/reload validation only.
Standalone zone skeletons may temporarily have no thermostat or source bindings,
while complete configuration graphs remain strict. It did not add thermostat
selection, temperature or humidity source selection, entity validation, device
creation, entities, coordinator behavior, persistence Store, options flow,
parent reconfiguration, aggregation, service calls, or physical control.

## 5. Entity Selection and Validation

Purpose: Allow selection and validation of source entities needed for
observation.

Included scope: Thermostat and temperature source references, duplicate checks,
domain compatibility, and entity-existence validation.

Explicit exclusions: Capability discovery, subscriptions, registry mutation,
aggregation, and control.

Dependencies: Zone creation and stable identifiers.

Acceptance criteria: Invalid or duplicate selections are rejected before setup.

Required tests: Missing entity, wrong domain, duplicate thermostat ownership
stub, duplicate source binding, and valid one-thermostat selection.

Safety impact: Prevents ambiguous ownership and bad source config.

Observation-only: Yes.

Status: Implemented. This task added one existing `climate` thermostat per new
equipment-group entry, exclusive thermostat ownership validation, and one or
more existing temperature sources per new zone. Climate sources bind to
`current_temperature`; sensor sources require the public temperature device
class and bind to state. Entity existence is required while `unknown` and
`unavailable` states remain valid configuration. Zone reconfigure preserves
stable source IDs and metadata for retained bindings. Setup validates the
persisted graph and retains only narrow compatibility for completely empty Task
4 binding skeletons; partially bound documents fail closed. It added no runtime
capability discovery, source observation or normalization, subscriptions,
registry mutation, aggregation, coordinator, devices, entities, Store,
services, or physical control.

## 6. Runtime Capability Discovery

Purpose: Discover thermostat capabilities from public Home Assistant state and
feature attributes.

Included scope: Read-only capability model, missing capability representation,
and no inference of stages or auxiliary heat.

Explicit exclusions: Command decisions, entity platforms, and vendor-specific
private APIs.

Dependencies: Entity selection and validation.

Acceptance criteria: Capabilities reflect observed public HA data only.

Required tests: Generic climate fixtures, unavailable thermostat, missing
stage/auxiliary as not observable, and conflicting target semantics.

Safety impact: Avoids unsupported future commands.

Observation-only: Yes.

Status: Implemented. This task added immutable thermostat capability and
discovery-status models plus a pure function that reads only generic public Home
Assistant climate state attributes. It normalizes HVAC modes, feature masks,
fan modes, and preset modes; distinguishes complete, partial, and unavailable
results; preserves both target feature flags when advertised; and treats
missing generic stage or auxiliary-heat data as not observable. It added no
vendor-specific inference, runtime subscriptions, coordinator, entity
platforms, persistence, registry mutation, command decisions, services, or
physical control.

## 7. Sensor Observation and Normalization

Purpose: Read configured source states and normalize temperature/humidity values.

Included scope: Unit conversion, calibration offsets, numeric validation, and
source observation records.

Explicit exclusions: Freshness, outlier rejection, aggregation, entities, and
persistence.

Dependencies: Entity selection and validation.

Acceptance criteria: Supported units normalize deterministically; invalid values
are excluded with reason codes.

Required tests: Celsius, Fahrenheit, unknown, unavailable, nonnumeric,
nonfinite, unsupported unit, and calibration.

Safety impact: Prevents malformed values from entering later calculations.

Observation-only: Yes.

Status: Implemented. This task added immutable generic source observations,
the approved source-quality and exclusion-reason vocabularies, and pure
normalizers over caller-supplied Home Assistant `State` objects. Temperature
sensor states use their public `unit_of_measurement`; climate
`current_temperature` values are already serialized into Home Assistant's
configured temperature unit, so the pure boundary requires that public unit
context explicitly from a future caller and fails closed when it is missing or
invalid. Home Assistant's converter normalizes supported values to Celsius;
humidity values use percentage points; calibration follows unit normalization;
and raw values remain distinct from normalized values. Missing, unknown,
unavailable, nonnumeric, nonfinite, and unsupported-unit inputs are excluded
deterministically. The supported restored marker is recorded but not rejected.
It added no runtime wiring, subscriptions, freshness, plausibility, jump,
restored health, outlier, minimum-count, aggregation, coordinator, entities,
persistence, diagnostics, Repairs, services, or physical control.

## 8. Sensor Freshness and Health

Purpose: Add source health evaluation for stale, restored, implausible, and jump
values.

Included scope: Freshness thresholds, plausible bounds, restored-state handling,
jump detection, and deterministic clocks.

Explicit exclusions: Aggregation, coordinator, Store, and entity publication.

Dependencies: Sensor observation and normalization.

Acceptance criteria: Suspicious values are excluded and never reused as public
effective values.

Required tests: Stale values, restored values, implausible values, jump
rejection, and confirmed recovery.

Safety impact: Blocks bad readings before public observation.

Observation-only: Yes.

Status: Implemented. This task added frozen, slotted pending-jump and health
result models plus pure temperature and humidity health evaluators over
caller-supplied observations, timestamps, accepted baselines, and pending
state. Processing rejects implausible values, restored values, and stale values
in the approved order before applying temperature rate-of-change checks.
Configured temperature bounds and the fixed 0–100 humidity range are inclusive;
freshness excludes only ages strictly beyond the threshold and treats future
source timestamps as age zero. Accepted baselines use the accepted source's
`last_reported` time. Excessive temperature changes require a consistent second
reading at least 30 seconds later; returning to the baseline range recovers
immediately and changing the candidate restarts confirmation. All Task 7 and
Task 8 exclusions recover deterministically without replacing or leaking the
last accepted value. The task reads no clock and adds no cross-source outlier
or contradiction handling, minimum counts, aggregation, runtime invocation,
subscriptions, timers, coordinator, Store access, persistence, options flow,
entities, devices, diagnostics, Repairs, services, commands, or physical
control.

## 9. Outlier Rejection and Aggregation

Purpose: Produce effective zone temperature and humidity from valid sources.

Included scope: Mean, median, weighted average, priority, MAD outlier handling,
two-sensor contradiction behavior, and minimum valid counts.

Explicit exclusions: Occupied-room, warmest/coldest-room strategies, entities,
and control.

Dependencies: Sensor freshness and health.

Acceptance criteria: Aggregates are deterministic and degraded states have clear
reasons.

Required tests: One, two, three, and many-source aggregation; contradictory
sensors; weights; priority source; minimum count failure.

Safety impact: Prevents a single bad source from defining zone conditions.

Observation-only: Yes.

Status: Implemented. This task added frozen, slotted aggregation results with
healthy, degraded, and unavailable states and deterministic configured-order
source accounting. Temperature performs one MAD pass for three or more
otherwise-valid sources, using
`max(outlier_floor_c, 3 × 1.4826 × MAD)` and the configured floor when MAD is
zero; only values strictly beyond the threshold are excluded. Two
otherwise-valid sources become contradictory only beyond twice the floor. A
unique smallest positive priority may supply a degraded fallback when the
minimum count permits one source; zero means unconfigured and tied best
priorities are ambiguous. Minimum-valid counts follow filtering, and mean,
median, normalized weighted-average, and explicit-priority strategies are
supported. Successful temperatures use Python's one-decimal `round` only after
calculation. Humidity uses the same strategies and minimum enforcement without
a fabricated Celsius MAD/contradiction threshold or temperature rounding.
Earlier source-health exclusions pass through unchanged. The task added no
state lookup, normalization, health reevaluation, runtime wiring, subscriptions,
coordinator, snapshot, Store access, persistence, options flow, entities,
devices, diagnostics, Repairs, activity history, services, command decisions,
or physical control.

## 10. Observe-Only Coordinator

Purpose: Add event-driven runtime orchestration for observation.

Included scope: Entry runtime, source subscriptions, debounce, affected-zone
reevaluation, snapshots, and unload cleanup.

Explicit exclusions: Entities beyond what is needed for testing, diagnostics,
Repairs, Store writes, and command execution.

Dependencies: Aggregation and capability discovery.

Acceptance criteria: Coordinator evaluates only affected zones and unloads all
listeners/timers.

Required tests: State changes, coalescing, reload, unload, no blocking I/O, and
no service calls.

Safety impact: Centralizes observation without control.

Observation-only: Yes.

Status: Implemented. This task added a typed config-entry runtime configuration
and event-driven `DataUpdateCoordinator` stored only in
`ConfigEntry.runtime_data`. It builds deterministic source-to-zone and
thermostat-to-zone indexes, registers indexed state-change and state-report
subscriptions over the unique enabled-source/thermostat union, coalesces report
bursts, refreshes changed
thermostat capability/public-state snapshots, and reevaluates only affected
zones while preserving unaffected immutable snapshots. It invokes the existing
Task 6-9 normalization, health, jump, MAD/contradiction, minimum-count, and
aggregation boundaries. Initial snapshots reconcile all configured inputs;
one earliest-deadline watchdog reevaluates accepted sources after the strict
freshness boundary; and unload/reload cancels all owned subscriptions and
timers without retaining baselines or pending candidates. Disabled observation
the narrow Task 4 empty skeleton, and awaiting-first-zone parents create no
subscriptions or timers. It
added no entity platforms, devices, Store persistence, diagnostics, Repairs,
history/events, services, command decisions, command sinks, or physical
control. Live observation remains internal until Task 11.

## 11. Read-Only Zone Climate Entity

Purpose: Expose observed zone conditions through a virtual climate entity.

Included scope: Current temperature, humidity when available, observed mode and
action when unambiguous, no writable features, translated setter errors.

Explicit exclusions: Target changes, fan/preset changes, schedules, predictive
attributes, and placeholder entities.

Dependencies: Observe-only coordinator.

Acceptance criteria: Entity is read-only and never changes physical equipment.

Required tests: Entity inventory, supported features equals zero, setter errors,
single thermostat values, conflicting thermostat values.

Safety impact: Provides user surface without writable control.

Observation-only: Yes.

Status: Implemented. This task added exactly one coordinator-backed read-only
`climate` entity per configured non-skeleton zone, stable `<zone_id>:zone`
unique IDs, exact config-subentry association, and integration-owned
equipment-group and child zone devices. The entity presents effective
temperature, optional humidity, common available-thermostat mode/action, and a
single target or target range only when every bound thermostat is available and
agrees within an inclusive 0.1°C span. It uses Home Assistant display-unit
conversion, strict current-snapshot availability, no polling, and the normal
coordinator listener update path. Its supported-feature mask is exactly zero,
and every supported asynchronous climate setter raises a translated
observation-only validation error without executor, coordinator, service,
command, or physical side effects. Setup and unload forward only the climate
platform and preserve a live coordinator when platform unload fails. It added
no sensor, binary-sensor, switch, event, placeholder, diagnostics, Repairs,
Store, persistence, history, schedules, predictions, decisions, services,
commands, or physical control.

## 12. Diagnostics and Redaction

Purpose: Provide safe diagnostic downloads.

Included scope: Redacted config/runtime summaries, hashed entity references,
capability flags, source-quality summaries, and forbidden-string tests.

Explicit exclusions: Repairs, activity UI, and unbounded raw state dumps.

Dependencies: Coordinator and capability/source snapshots.

Acceptance criteria: Diagnostics contain no raw entity IDs, names, device IDs,
area IDs, context/user IDs, tokens, URLs, or coordinates.

Required tests: Snapshot redaction, forbidden-string scans, allowed-value checks.

Safety impact: Enables troubleshooting without leaking sensitive data.

Observation-only: Yes.

Status: Implemented. This task added Home Assistant config-entry diagnostics
schema version 1 with a strict typed allowlist projection over decoded
configuration and the current immutable coordinator snapshot. Reports include
integration/config-entry versions, bounded decode and runtime-configuration
state, equipment/zone/source structure, safe observation options, thermostat
availability and approved capability/observed-state fields, effective zone
values, aggregation state/reasons, and configured-order source-quality and
exclusion-reason summaries. Valid unloaded, awaiting-first-zone, transitional
empty-skeleton, disabled-observation, and failed-decode entries return bounded
safe reports without requiring runtime data or exposing malformed input.

Every report receives a new secret 32-byte random salt. Entity references and
user-assigned entry/group/zone names use cached report-scoped HMAC-SHA256
pseudonyms that are consistent only within that report; the salt is never
returned. Config-entry IDs/unique IDs, raw entity IDs/names, registry and
context/user/account identifiers, credentials, locations, coordinates,
addresses, URLs, private keys, paths, raw states/values, and arbitrary
attributes are omitted by construction. Home Assistant redaction is applied
only after the explicit allowlist as defense in depth.

The task added no Store load/write, Repairs issue, activity history/event,
entity or platform, polling, service, command, schedule, prediction, timer,
subscription, runtime mutation, or physical control. Device-specific
diagnostics remained absent at Task 12 completion; the later Task 14 status
below records the approved activity/Store implementation.

## 13. Repairs Integration

Purpose: Report actionable configuration and runtime problems.

Included scope: Missing entity, incompatible entity, migration failure, repeated
Store failure, and command-boundary violation issue codes.

Explicit exclusions: Automated repair actions that mutate configuration unless
separately designed.

Dependencies: Diagnostics and configuration validation.

Acceptance criteria: Issues are created and cleared deterministically.

Required tests: Issue lifecycle for each supported problem and translation keys.

Safety impact: Makes unsafe or broken observation states visible.

Observation-only: Yes.

Status: Implemented. This task added a typed entry-scoped Repairs manager using
Home Assistant 2026.7's supported issue-registry callbacks. Issue IDs use
`entry_<12 lowercase SHA-256-derived hex>_<issue_code>` and never contain raw
entry IDs, entity IDs, names, group/zone UUIDs, or Python `hash()` output. Every
issue uses current-error severity and `is_fixable=False`.

Supported lifecycle:

- `missing_entity` is nonpersistent and aggregated once per entry. It is
  evaluated only after startup reconciliation completes, covers a missing
  configured thermostat or enabled temperature/humidity source State, ignores
  existing unknown/unavailable States, and clears when no evaluated reference
  is missing. Disabled observation deliberately does not evaluate sources.
- `incompatible_entity` is nonpersistent and aggregated once per entry. It is
  created only for a definitive existing binding conflict, such as an
  available sensor with the wrong device class, not for missing optional
  climate attributes or ordinary source-quality states. It clears when all
  evaluated bindings are compatible.
- `migration_failed` is persistent. Known config/schema migration and
  fail-closed persisted-validation boundaries create it before setup aborts
  using a bounded failure category, and a later successfully validated setup
  clears it.
- `store_write_failed` is persistent. Task 13 provides a typed hook that
  creates it at three or more consecutive failures and clears it on a
  successful/reset notification. No runtime Store load, write, retry, timer,
  task, or filesystem behavior was added; wiring remains deferred to the
  approved Store/lifecycle task.
- `command_boundary_violation` is persistent. A nonempty intent reaching the
  observe-only sink remains suppressed, logs only a stable reason, creates a
  payload-free issue, and makes no service call or physical command. A later
  clean setup clears a stale event issue before observation and another
  violation recreates it.

Coordinator synchronization reuses reconciliation, targeted state events, and
the existing watchdog evaluation; it adds no subscription, polling loop, or
recurring callback. Unload cleans coordinator callbacks but does not delete a
still-valid persistent event issue. Diagnostics schema version 1 now permits a
backward-compatible `runtime.repairs.active_issue_codes` list containing only
sorted stable codes. English issue titles/descriptions are supplied through the
established custom-integration `translations/en.json` `issues` section.

Task 13 added no automatic RepairsFlow, fix flow, configuration mutation,
physical command adapter, service call, writable entity, Store persistence,
activity history, or new entity platform at its completion. The later Task 14
status below records the approved activity/Store implementation.

## 14. Bounded Event and Activity History

Purpose: Preserve material observation activity without unbounded growth.

Included scope: Activity records, Event entities, event-bus payloads, Logbook
visibility, pruning by count and age.

Explicit exclusions: Custom frontend panel and high-frequency raw observations.

Dependencies: Coordinator and Store schemas.

Acceptance criteria: Only material changes are recorded; history is bounded.

Required tests: Activity creation, no duplicate unchanged entries, pruning,
event payload redaction, unload save behavior.

Safety impact: Improves explainability without control.

Observation-only: Yes.

Status: Implemented. This task added strict privacy-bounded activity records,
an entry-scoped age/count-bounded history with a 500-record hard cap, semantic
materiality over coordinator and non-coordinator transitions, one
`intelligent_climate_activity` bus event per newly accepted record, one
diagnostic equipment-group Activity Event, one diagnostic Activity Event and
Latest Activity sensor per configured zone, and a backward-compatible
diagnostics schema version 1 activity/Store-health projection.

Runtime Store v1 now loads and writes the existing `decisions` field as strict
activity records at `intelligent_climate.<entry_id>` using Home Assistant Store
version 1 and atomic writes. Normal saves occur only after material activity
with a 30-second debounce, five-minute maximum dirty interval, one writer, and
bounded retry. Unload records activity and attempts a clean save for no more
than five seconds. The Store saves current zone values and source baselines but
Task 14 restores only bounded activity; persisted temperatures and baselines
never enter live coordinator/entity state. `command_journal` remains empty.

The task added no Store migration/quarantine/reconciliation hardening reserved
for Task 15, no custom Logbook duplicate, no extra Phase 1 entity surface, no
schedule, override, occupancy, window behavior, model, prediction, simulation,
service call, physical adapter, writable capability, or physical control.

## 15. Config-Entry Migration, Reload, and Recovery Testing

Purpose: Harden lifecycle behavior before declaring Phase 1 complete.

Included scope: Entry migration, Store migration, corrupt Store handling,
startup reconciliation, reload, unload, and Home Assistant restart behavior.

Explicit exclusions: New features beyond lifecycle hardening.

Dependencies: Store schemas, coordinator, diagnostics, Repairs, activity
history.

Acceptance criteria: Invalid migration fails closed; restart never publishes
unconfirmed restored values or queues commands.

Required tests: Successful migration, failed migration, corrupt Store, missing
Store, startup reconciliation, reload/unload leak checks.

Safety impact: Protects restart and upgrade paths.

Observation-only: Yes.

Status: Implemented. Config entries migrate transactionally from 1.0 to 1.1:
the complete parent, options, and zone graph is decoded and validated before
one parent update. Any invalid or future graph remains unchanged and creates
the existing bounded migration Repair.

The Home Assistant Store envelope migrates canonically from 1.1 to 1.2 while
Store major version 1, inner `schema_version: 1`, `decisions`, and the empty
`command_journal` remain unchanged. Valid history and configured-source
baselines restore; baselines are comparison-only inputs to live reconciliation.
Persisted zone observations never become coordinator or public entity state.

Missing Store data starts empty. Semantically invalid data is retained in one
entry-scoped quarantine and is replaced only after a successful clean save.
Future or unreadable envelopes are preserved read-only. Diagnostics expose
only bounded recovery health, and Repairs/activity receive stable categories
without malformed payloads or exception text.

Reload, failed platform unload, clean unload, restart, pending debounce,
multiple-entry isolation, and callback/task cleanup are covered without
changing entity inventory or adding a service call, writable capability,
schedule, prediction, simulation, adapter, or physical control.

Release 0.0.7 corrects full-core restart detection by registering one supported
Home Assistant shutdown job per loaded entry. The awaited job performs the
verified bounded clean save and releases entry-scoped runtime callbacks before
core shutdown continues. Repeated final-save requests are idempotent, ordinary
unload removes the job after successful platform unload, and failed unload
preserves it.

## 16. Phase 1 Integration and Acceptance Testing

Purpose: Prove the complete Phase 1 observation baseline meets the accepted
design.

Included scope: Full Phase 1 acceptance criteria review, coverage gate,
hassfest, HACS validation, docs review, and supplied Nest fixture if available.

Explicit exclusions: Phase 2 or later functionality.

Dependencies: All prior Phase 1 tasks.

Acceptance criteria: Every approved Phase 1 criterion passes with automated or
documented manual evidence.

Required tests: Complete no-command suite, full config-flow coverage, entity
inventory, diagnostics redaction, lifecycle, and deterministic fixture tests.

Safety impact: Release gate for observation-only Phase 1.

Observation-only: Yes.

Status: Implemented in release-candidate 0.0.8. Automated acceptance evidence
passes for P1-AC-001 through P1-AC-035; P1-AC-003 and P1-AC-026 additionally
require their documented Home Assistant UI walkthroughs before final Phase 1
acceptance.

Release 0.0.8 completes atomic first-zone setup, multi-thermostat independent
and shared/zoned configuration, parent and zone reconfiguration, all safe
options, the exact Phase 1 entity matrix, guarded degraded-state recovery,
reason-coded/cooldown-bounded logging, the supplied sanitized Nest fixture, and
network-isolated acceptance gates. It adds no Phase 2 behavior or physical
command path.

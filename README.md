# Intelligent Climate

Intelligent Climate is a local-first climate-management integration for Home
Assistant.

## Status

Pre-alpha. The project currently contains the repository foundation, strict
typed schema models for future configuration and runtime Store documents, and
a Home Assistant UI flow for creating one equipment group with exactly one
existing `climate` thermostat, followed by native zone config-subentry add and
reconfigure flows. Zones use immutable UUIDv4 identifiers that remain stable
across display-name changes and reloads.

Task 11 adds exactly one visible read-only Home Assistant `climate` entity for
each configured zone. Each entity has the stable unique ID `<zone_id>:zone`,
belongs to its exact zone config subentry, and is attached to a virtual zone
device beneath the integration-owned equipment-group device. Zone and
equipment-group names may change without changing their stable registry
identifiers. The integration does not claim physical thermostat devices or
create devices for source sensors.

The zone climate surface presents the coordinator's effective temperature and
optional effective humidity. It reports HVAC mode and action only when the
currently available bound thermostats agree. A single target or target range is
shown only when every bound thermostat is available, uses the same target
representation, and agrees within an inclusive 0.1°C span. Home Assistant
converts the integration's Celsius temperature values into the installation's
configured display unit.

Availability is strict: the coordinator must be healthy, the current snapshot
must contain the zone, reconciliation must be complete, observation must be
enabled, an effective temperature must exist, and at least one bound thermostat
must be available. A degraded aggregation remains available when it still
provides a valid effective temperature. Previously valid values are never
reused when the current snapshot has no effective temperature.

The entity always advertises `ClimateEntityFeature(0)`. Its HVAC-mode list
contains only the current unambiguous observed mode, or is empty when ambiguous.
Observed targets use bounded standard state attributes without enabling
writable target features. Every supported asynchronous climate setter
immediately raises a translated observation-only `ServiceValidationError`;
there is no executor fallback, service call, command sink, or physical-control
path.

The underlying Task 10 entry-scoped, event-driven observation coordinator
remains stored as typed `ConfigEntry.runtime_data`. Setup decodes the parent,
zones, and options once into an immutable runtime configuration, builds
deterministic source-to-zone and thermostat-to-zone indexes, and subscribes
to both state-change and state-report events for the unique union of enabled
sources and configured thermostats. Relevant report bursts are coalesced, only
affected zones are reevaluated, and unchanged zone snapshot objects and
timestamps are retained.

The coordinator invokes the existing Task 6-9 boundaries for public thermostat
capability/state snapshots, source normalization, health evaluation, outlier
rejection, and aggregation. It publishes frozen entry and zone snapshots with
strict revision semantics, performs startup reconciliation without accepting
restored values, and uses one earliest-deadline watchdog so a source becomes
stale even without another report. Disabled observation, the narrow empty Task
4 skeleton, and a valid parent awaiting its required first zone install no
subscriptions or timers. The awaiting-first-zone snapshot is empty,
non-reconciling, and `initializing`; platform setup creates no zone entity or
orphan entity-registry record. Unload and reload cancel both subscriptions,
debounce callbacks, reconciliation, and freshness deadlines without carrying
baselines or pending jump candidates into the new runtime.

Version 0.0.2 separates interactive entity validation from persisted startup
validation. New thermostat and zone-source selections still require current
Home Assistant states, correct domains, and a temperature device class for
sensor sources. During entry setup, persisted entity references are validated
structurally instead: they must have valid entity IDs, supported domain and
attribute bindings, stable source identities, correct parent/zone
relationships, and exclusive thermostat ownership, but their integrations do
not need to have loaded yet.

A zone may therefore start unavailable while a configured thermostat or
temperature source is absent, unavailable, unknown, disabled, restoring, or
still loading. The coordinator subscribes to the persisted entity IDs without
polling; state-change and state-report events automatically reevaluate the
affected zone when those entities appear. The read-only zone climate entity
then recovers without an options edit, config-entry reload, or another Home
Assistant restart. This startup-ordering behavior remains strictly
observation-only and never calls a Home Assistant service to control equipment.

Task 11 creates no sensor, binary-sensor, switch, event, equipment-group status,
or placeholder entities. There is still no Store load or write, persistence,
diagnostics, Repairs, activity history/event publication, integration service
registration, command decision, command invocation, or physical control.

This is the first Task 11 build suitable for an initial real Home Assistant
installation to verify live zone discovery and calculated temperature,
humidity, mode, action, and target observations while continuing to use the
original thermostat for all control.

Task 9 adds pure effective-temperature and effective-humidity calculation over
the immutable observations produced by Tasks 7 and 8. Enabled sources are
matched exactly by stable source ID, earlier exclusions pass through unchanged,
and disabled sources are absent from source accounting. Results report every
valid, contributing, fallback, and excluded source in deterministic configured
order with healthy, degraded, or unavailable status.

Temperature uses one deterministic MAD pass when three or more otherwise-valid
sources exist. A source is excluded only when its absolute deviation is
strictly greater than `max(outlier_floor_c, 3 × 1.4826 × MAD)`; zero MAD uses
the configured floor and an exact threshold value remains valid. Two
otherwise-valid temperatures are contradictory only when their spread is
strictly greater than twice the floor. Both remain contradictory, but a
degraded one-source fallback may use the unique smallest positive priority when
the minimum count permits one source. Priority zero means unconfigured, and a
tied best positive priority is ambiguous.

Minimum-valid counts are enforced after source health and temperature
filtering. Mean, mathematical median, normalized weighted average, and explicit
priority strategies are supported. Successful temperatures are rounded with
Python's `round(value, 1)` only after calculation; source values and spread are
not rounded. Humidity supports the same strategies and minimum counts without
inventing a Celsius-based MAD or contradiction threshold, and is not rounded by
Task 9.

Task 9 remains a pure, caller-invoked calculation boundary. It adds no live
state lookup, runtime subscriptions, coordinator, snapshots, Store access,
persistence, options flow, entities, diagnostics, Repairs, service calls,
command decisions, or physical control. Automatic runtime invocation and the
complete zone observation belong to Task 10.

Task 8 adds pure source-health evaluation over Task 7 observations and
caller-supplied timestamps. Temperatures outside the configured inclusive
Celsius range and humidity outside the fixed inclusive 0–100 percentage-point
range are rejected as implausible. Restored values remain excluded until a
non-restored live observation arrives. Source freshness uses the difference
between the injected observation time and Home Assistant's actual
`State.last_reported` time. An unchanged reading remains valid when its
integration has reported it recently, while a genuinely unreported source
becomes stale only when its age is strictly greater than the configured
threshold. Future source timestamps are treated as age zero.

Accepted values establish or update an immutable source baseline using the
source report timestamp. Temperature changes are limited by the configured
Celsius-per-five-minutes rate. A reading beyond that range is held in immutable
pending-candidate state and can establish a new range only when a second
consistent reading arrives at least 30 seconds later. Returning to the accepted
baseline range recovers immediately, while a different suspicious range
restarts confirmation. Rejected observations never expose a previous baseline
as their current value.

Task 8 does not run automatically and adds no subscriptions, timers, Store
access, or persistence. Cross-source outlier rejection, contradiction handling,
minimum-valid-source checks, and aggregation remain Task 9 work. Coordinator
and runtime invocation remain Task 10 work. No entities, diagnostics, Repairs,
service calls, command decisions, or physical control are included.

Task 7 provides the preceding pure per-source observation boundary over
supplied public Home Assistant `State` objects. It preserves raw values and
stable source IDs in immutable typed records, parses finite numeric values,
converts supported temperature units to Celsius, treats humidity as percentage
points, and applies per-source calibration only after unit normalization.
Missing, unknown, unavailable, nonnumeric, nonfinite, and unsupported-unit
values are excluded with stable quality and reason codes rather than replaced
with zero.

State-based sensors use the public `unit_of_measurement` attached to their
published state. Climate `current_temperature` values are already serialized
into Home Assistant's configured temperature unit, but climate states do not
generically publish that unit as `unit_of_measurement`. The pure Task 7 boundary
therefore requires a future caller to supply the configured climate temperature
unit explicitly. Missing, malformed, or unsupported climate unit context fails
closed as `unit_unsupported`. The restored-state marker is recorded without
rejection in Task 7 and enforced by the separate Task 8 health boundary.

Task 6 adds pure, read-only thermostat capability discovery from public Home
Assistant `State` attributes. It normalizes supported HVAC modes and
`ClimateEntityFeature` masks into an immutable typed model, reports discovery
as complete, partial, or unavailable, and retains target-temperature and target
range flags independently when both are advertised. That conflicting dual
target advertisement is retained without choosing one semantic and is reported
as partial. Missing, malformed, future-unknown, or feature/list-inconsistent
public capability data also produces a partial result; missing, unknown, or
unavailable state produces an unavailable result without fabricated
capabilities.

Stage and auxiliary-heat observability remain false because Home Assistant
2026.7.3 exposes no generic public climate attribute for either condition.
Vendor-specific fields, equipment type, current HVAC mode, and HVAC action do
not change that result. Capability discovery is not yet wired to setup,
subscriptions, automatic refresh, a coordinator, or runtime storage.

Task 5 adds backend-authoritative entity selection and validation. Each new zone
automatically uses its parent's one thermostat and requires one or more existing
temperature sources. Supported sources are `climate` entities bound to
`current_temperature` and `sensor` entities with the public temperature device
class. An `unknown` or `unavailable` state still proves that a configured entity
exists; runtime availability and capability evaluation are intentionally
deferred.

Zone reconfiguration preserves the stable source UUID and all calibration,
weight, priority, and enabled metadata for every retained `(entity_id,
attribute)` binding. Pre-Task-5 parents and zones that are completely empty
binding skeletons remain loadable, but partially bound legacy documents fail
closed. A structurally valid parent with its one validated primary thermostat
and no zones is an explicit awaiting-first-zone state. Completing any zone add,
including the mandatory first zone, automatically schedules exactly one parent
reload after Home Assistant commits the new subentry, so no manual reload is
needed. Because this task adds no parent reconfigure flow, a pre-alpha skeleton
parent must be removed and recreated to complete Task 5 selection.

It does not subscribe to, aggregate, or expose source values. It also does not
provide registry rename handling or mutation, device or entity creation, a
coordinator, Store persistence, options or parent reconfiguration, diagnostics,
scheduling, modeling, simulation, service calls, or physical control.

It must not be used to control production HVAC equipment. The current code is
strictly observation-only and contains no Home Assistant service-call path for
changing climate-related equipment.

## Documentation

- Product specification: `docs/product-specification.md`
- Phase 1 technical design: `docs/phase-1-technical-design.md`
- Development guide: `docs/development.md`
- Phase 1 non-goals: `docs/non-goals-phase-1.md`
- Implementation backlog: `docs/implementation-backlog.md`
- Licensing options: `docs/licensing-options.md`
- ADRs: `docs/adr/`

## License

This public source snapshot is licensed under the
[PolyForm Strict License 1.0.0](LICENSE).

The license permits qualifying noncommercial use but does not grant permission
to distribute copies, modify the software, or create derivative works.
Intelligent Climate is source-available software; it is not released under an
open-source license.

Copyright © 2026 Michael Wells.
## Development

Development is performed incrementally using the authoritative project
documents and automated testing.

The repository foundation provides:

- Home Assistant custom-integration package skeleton for the
  `intelligent_climate` domain.
- Minimal config-entry setup and unload lifecycle functions.
- Minimal typed identifiers, operating-mode terminology, and strict schema
  boundary helpers.
- A UI config flow that records an equipment-group name and equipment type,
  validates one exclusively owned climate thermostat, generates a stable UUID,
  then chains to a native first-zone subentry flow.
- Native zone add and reconfigure flows with temperature-source selectors,
  normalized display names, per-parent duplicate-name checks, stable zone and
  retained-source UUIDv4 identities, and fail-closed setup validation.
- Pure public-state thermostat capability discovery with immutable complete,
  partial, and unavailable results and no vendor-specific stage or auxiliary
  inference.
- Pure source observation and normalization with immutable raw/normalized
  records, Celsius and humidity percentage-point normalization, calibration,
  and explicit invalid-value reason codes.
- Pure source freshness and health evaluation with plausible ranges,
  restored-value exclusion, strict freshness boundaries, immutable accepted
  baselines, temperature jump candidates, and 30-second confirmation.
- Pure immutable temperature and humidity aggregation with deterministic source
  accounting, temperature MAD rejection, two-source contradiction handling,
  minimum-valid counts, and mean, median, weighted, and explicit-priority
  strategies.
- Typed config-entry runtime data with indexed live state subscriptions,
  affected-zone coalescing, immutable entry/zone/thermostat snapshots, startup
  reconciliation, freshness deadlines, and complete unload/reload cleanup.
- One coordinator-backed, nonpolling read-only climate entity per configured
  zone, with stable zone-based unique IDs, exact config-subentry ownership,
  integration-owned equipment/zone devices, strict availability, unit-aware
  temperature and target presentation, consensus mode/action/target
  observations, zero writable features, and translated setter rejection.
- An observation-only command boundary that suppresses future command intents.
- Tests that fail if integration Python code introduces a
  `hass.services.async_call` path.

Run local checks with:

```powershell
python -m pytest --cov=custom_components.intelligent_climate --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m mypy custom_components/intelligent_climate tests
```

# Intelligent Climate

Intelligent Climate is a local-first Home Assistant integration that combines
trusted temperature sources into a read-only climate view for each configured
zone. It helps you understand current conditions and source health while you
continue to control heating and cooling through the original thermostat.

> [!IMPORTANT]
> **Intelligent Climate is observation-only in Phase 1.** It does not change a
> thermostat, fan, switch, humidifier, dehumidifier, ventilation system, water
> heater, or other physical equipment. The integration makes no
> climate-related service call. Continue using your original thermostat entity
> for every control action.

## Current release and maturity

The current release is **0.0.3**. Intelligent Climate is pre-alpha software
intended for careful evaluation on a current Home Assistant installation. Its
observation pipeline, read-only zone climate entities, startup recovery, and
redacted diagnostics are implemented and tested. Later phases remain under
active design and development.

## Recent changes

- **0.0.3**
  - Added redacted downloadable diagnostics.
  - Reorganized the README for integration users and converted the release
    history into a versioned changelog.
- **0.0.2**
  - Valid persisted entities no longer fail only because their integrations
    load later during Home Assistant startup.
  - Zones recover automatically through state events when those entities
    appear.
- **0.0.1**
  - Corrected the first-zone setup race.
  - Changed source freshness from `last_updated` to `last_reported`, so an
    unchanged value remains fresh when its integration has reported it
    recently.

[View the full changelog](CHANGELOG.md)

## What Intelligent Climate does today

Intelligent Climate currently provides:

- UI-based setup for an HVAC equipment group with one existing Home Assistant
  `climate` thermostat.
- Native zone add and reconfigure flows.
- One read-only virtual `climate` entity for every configured zone.
- Zone temperature calculated from one or more configured temperature sensors
  or a thermostat's public `current_temperature` attribute.
- Optional humidity aggregation when humidity sources are configured.
- Observed HVAC mode, action, and target information when the bound thermostat
  data is available and unambiguous.
- Event-driven recovery when a configured thermostat or source loads after the
  Intelligent Climate entry.
- Source freshness, plausibility, restored-state, jump, contradiction, and
  outlier checks.
- Privacy-preserving downloadable diagnostics for configuration and current
  runtime health.

The original thermostat remains independently available and is the only
supported way to change HVAC settings.

## What it deliberately does not do

Phase 1 does not provide:

- Thermostat, fan, switch, humidity, ventilation, or other equipment control.
- Schedules, manual overrides, occupancy control, or window suspension.
- Predictive control, adaptive start or stop, thermal models, or simulation.
- Equipment arbitration, heat-pump optimization, or auxiliary-heat logic.
- Sensor, binary-sensor, switch, event, diagnostics-device, or frontend
  entities beyond the read-only zone climate entity.
- Runtime Store persistence, Repairs issues, or activity history yet.

Unavailable or questionable observations are excluded instead of being
replaced with invented values. Intelligent Climate never substitutes a stale
persisted temperature into the public zone entity.

## Installation with HACS

Intelligent Climate is structured as a HACS custom integration.

1. Open HACS in Home Assistant and select **Integrations**.
2. Open the HACS menu and choose **Custom repositories**.
3. Paste
   `https://github.com/GoHoos1/intelligent-climate-public`
   and select **Integration** as the category.
4. Find **Intelligent Climate** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings > Devices & services > Add integration**, search for
   **Intelligent Climate**, and begin setup.

Use the public repository URL above when adding the HACS custom repository.

## Initial setup

The setup flow asks for:

1. An equipment-group display name and descriptive equipment type.
2. One existing thermostat entity from the `climate` domain.
3. A first-zone display name.
4. One or more existing temperature sources.

A temperature source can be:

- A temperature `sensor` entity, using its state and published unit.
- A `climate` entity, using its public `current_temperature` attribute.

The selected thermostat and sources must exist during interactive setup.
Unknown or unavailable entities can still be selected when Home Assistant has
already created their state. Intelligent Climate then evaluates their actual
health at runtime.

After setup, use the original thermostat entity whenever you want to change the
mode, target, preset, fan setting, or any other physical behavior.

## Adding and reconfiguring zones

Open the Intelligent Climate entry under **Settings > Devices & services**.
Use the entry's zone/subentry controls to add another zone. Use a zone's
reconfigure action to change its name or temperature sources.

Zone and source identities are generated once and remain stable when display
names change. Retained source bindings preserve their calibration, weight,
priority, enabled state, and source identity.

The current relationship model assigns the equipment group's one thermostat to
each configured zone. Removing and recreating the parent entry is still
required for parent-level equipment or thermostat changes that are not exposed
by the current reconfigure surface.

## Understanding the read-only zone climate entity

Every configured zone receives one virtual `climate` entity. It can show:

- The effective current temperature.
- Effective humidity when humidity sources are configured.
- The thermostat's observed HVAC mode and action.
- An observed target or target range when the bound thermostat data agrees.

The entity advertises no writable features. Attempts to use a climate setter
are rejected with an observation-only error and produce no service call.

A zone may temporarily be unavailable while its thermostat or sources are
missing, unavailable, unknown, restoring, stale, or still loading. It recovers
automatically after valid source reports arrive; no options edit, integration
reload, or Home Assistant restart should be necessary.

## Source health and availability

Intelligent Climate evaluates every enabled source before aggregation.
Depending on the current observation, a source can be excluded as:

- Missing or unavailable.
- Unknown.
- Nonnumeric or nonfinite.
- Using an unsupported temperature unit.
- Outside the configured plausible range.
- Stale.
- Restored but not yet confirmed by a live report.
- A large unconfirmed jump.
- A cross-source outlier.
- Contradictory with another source.

Freshness uses Home Assistant's `State.last_reported` timestamp. An unchanged
value therefore remains fresh when its integration has recently reported it.
A genuinely unreported value becomes stale after the configured threshold.

With three or more valid temperatures, one deterministic median-deviation pass
can exclude outliers. Two strongly disagreeing sources are marked
contradictory; a configured priority source can provide a degraded fallback
only when the minimum-source policy permits it. Mean, median, weighted average,
and priority aggregation are supported.

## Downloading diagnostics

To download diagnostics:

1. Go to **Settings > Devices & services**.
2. Open the Intelligent Climate integration entry.
3. Open the entry menu and choose **Download diagnostics**.

Diagnostics schema version 1 includes:

- Integration and config-entry schema versions.
- Configuration lifecycle state.
- Equipment-group and zone structure.
- Safe observation options.
- Thermostat availability, capability status, and approved observed values.
- Zone aggregation status and effective values.
- Configured-order source rows, quality counts, exclusion-reason counts, and
  safe report timestamps.

Every download uses a new random secret salt. Entity references and
user-assigned names become report-scoped HMAC-SHA256 pseudonyms. The salt,
config-entry ID, unique ID, raw entity IDs, raw names, state objects, arbitrary
attributes, device/area/context/user/account identifiers, credentials,
coordinates, URLs, and filesystem paths are not included.

Diagnostics are designed to reduce accidental disclosure, not to make a report
safe for every possible public context. **Review the downloaded file before
posting it publicly.**

## Troubleshooting

### The integration will not finish setup

Confirm that the persisted configuration is structurally valid and that the
selected thermostat belongs to only one Intelligent Climate entry. New
interactive selections must exist and use the supported domain or temperature
device class.

### The zone entity is unavailable after a restart

The thermostat or a source integration may still be loading. Intelligent
Climate subscribes to the configured entity IDs even when their states do not
exist yet. The zone should recover through the normal state event when those
entities appear.

### A source is stale even though its value did not change

Some integrations report unchanged readings less often than others. Check the
source's reporting behavior and increase the configured freshness threshold if
its normal report interval is longer. Recent unchanged reports are recognized
through `last_reported`.

### A source is excluded as jumping, contradictory, or an outlier

Check the physical sensor, unit, calibration, and update timing. A suspicious
jump needs a later consistent reading before it is accepted. Contradictory or
outlying values are not silently substituted.

### The thermostat can be changed but the zone entity cannot

That is expected. The zone entity is intentionally read-only. Use the original
thermostat entity for control.

When reporting a problem, include the integration version, a reviewed
diagnostic download, the expected behavior, and the relevant Home Assistant
logs without credentials.

## Privacy and local-first behavior

Observation and aggregation run locally inside Home Assistant. The integration
performs no network access for diagnostics and adds no cloud account. It reads
only the configured Home Assistant states needed for observation.

Normal diagnostic generation performs no polling, filesystem I/O, service
call, timer creation, subscription, reload, or runtime mutation. Raw Home
Assistant state objects and complete attribute mappings are never serialized.

## Current roadmap and Phase 1 status

Phase 1 is being delivered in small observation-only slices. Tasks 1 through 12
are implemented: repository and schema foundations, UI configuration, zone
identity, entity validation, capability discovery, source normalization and
health, aggregation, the event-driven coordinator, read-only zone climate
entities, and redacted diagnostics.

Remaining Phase 1 work includes Repairs integration, bounded activity history,
lifecycle/migration hardening, and final acceptance testing. Tasks 13 through
16 are not implemented. Scheduled control begins no earlier than Phase 2, and
predictive control remains a later phase.

See the [implementation backlog](docs/implementation-backlog.md) for the
approved sequence and explicit exclusions.

## Documentation

- [Product specification](docs/product-specification.md)
- [Phase 1 technical design](docs/phase-1-technical-design.md)
- [Implementation backlog](docs/implementation-backlog.md)
- [Phase 1 non-goals](docs/non-goals-phase-1.md)
- [Development guide](docs/development.md)
- [Architecture decisions](docs/adr/)
- [Full changelog](CHANGELOG.md)
- [Public source repository](https://github.com/GoHoos1/intelligent-climate-public)
- [Public issue tracker](https://github.com/GoHoos1/intelligent-climate-public/issues)

## Technical architecture

### Configuration and identity

One Home Assistant config entry represents one HVAC equipment group. Zones are
native config subentries. Equipment groups, zones, and sources use generated
UUIDs for stable integration identity; names and entity IDs remain
configuration references.

Persisted JSON is decoded through strict typed boundaries. Unknown fields,
invalid identifiers, duplicate sources, partial legacy graphs, and ambiguous
ownership fail closed. Config-entry major/minor versions remain `1.0` in
release 0.0.3; diagnostics do not change the persisted configuration schema and
require no migration.

### Lifecycle and observation

The entry stores one typed, event-driven coordinator in
`ConfigEntry.runtime_data`. It builds deterministic source-to-zone and
thermostat-to-zone indexes and listens for state-change and state-report events
over the configured observation set. Short bursts are coalesced, and only
affected zones are reevaluated.

Startup enters reconciliation, evaluates the current public states, and rejects
restored values until a live report arrives. One earliest-deadline watchdog
handles freshness without polling. Unload and reload cancel subscriptions,
debounce callbacks, reconciliation, and freshness deadlines.

### Aggregation behavior

Source extraction, health evaluation, capability discovery, aggregation, and
climate presentation are separate typed boundaries. Temperature values are
normalized to Celsius, calibrated, evaluated for health, filtered once for
outliers or contradiction, aggregated, and rounded to one decimal only after
calculation. Home Assistant converts the result to the installation's display
unit.

### Safety boundary

The integration package contains no active physical command adapter and no
direct `hass.services.async_call` path. The virtual climate entity advertises
`ClimateEntityFeature(0)`, and every supported setter raises a translated
validation error. Diagnostics are a read-only projection of already decoded
configuration and the current immutable coordinator snapshot.

## Development and validation

Use Python 3.14.2 or newer in a virtual environment, WSL2, or a dev container.
Do not install project dependencies into a global or per-user Python
environment.

```powershell
python -m pytest --cov=custom_components.intelligent_climate --cov-report=term-missing
python -m pytest tests/unit/test_no_physical_control_paths.py -q
python -m ruff check .
python -m ruff format --check .
python -m mypy custom_components/intelligent_climate tests
git diff --check
```

GitHub Actions run Quality and Hassfest automatically. HACS validation remains
manual-only through `workflow_dispatch`. See the
[development guide](docs/development.md) for environment details.

## License

This public source distribution is licensed under the
[PolyForm Strict License 1.0.0](LICENSE).

The license permits qualifying noncommercial use but does not grant permission
to distribute copies, modify the software, or create derivative works.
Intelligent Climate is source-available software; it is not released under an
open-source license. See [NOTICE](NOTICE) for the accompanying attribution and
distribution notice.

Copyright © 2026 Michael Wells.

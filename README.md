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

The current release is **0.0.8**. Intelligent Climate is pre-alpha software
intended for careful evaluation on a current Home Assistant installation. Its
observation pipeline, read-only zone climate entities, startup recovery, and
redacted integration diagnostics, Repairs notifications, and bounded activity
history are implemented and tested. Release 0.0.8 is the Phase 1 acceptance
candidate; final acceptance still requires the documented Home Assistant UI
walkthrough. Later phases remain under active design and development.

## Recent changes

- **0.0.8**
  - Completed atomic UI setup, parent/zone reconfiguration, safe options, and
    multi-thermostat independent/shared equipment graphs.
  - Added the exact Phase 1 condition, health, mode, configuration, and
    observation entity matrix.
  - Added guarded degraded-state recovery, stable reason-coded logs, an
    isolated Nest fixture, and network-isolated acceptance tests.
- **0.0.7**
  - Corrected normal Home Assistant restart detection by registering an awaited
    core-shutdown final save and releasing entry-scoped runtime callbacks.
  - Made the bounded clean-save path idempotent across core shutdown and
    ordinary integration unload.
- **0.0.6**
  - Added transactional config-entry 1.0-to-1.1 and Store-envelope 1.1-to-1.2
    migration with fail-closed validation and bounded quarantine.
  - Added comparison-only baseline restoration and restart/reload hardening;
    persisted temperatures still never become live public state.
- **0.0.5**
  - Added bounded, privacy-safe activity history with atomic Store v1
    persistence, Event entities, per-zone Latest Activity sensors, and one
    documented Home Assistant event-bus payload.
  - Added material-only source, thermostat, capability, Repairs, command
    boundary, Store-health, and lifecycle activity without adding control.
- **0.0.4**
  - Added deterministic, translated Repairs notifications for actionable
    entity, migration, Store-write, and command-boundary failures.
  - Added bounded active Repairs codes to diagnostics and corrected the
    documentation to distinguish integration data from Home Assistant's outer
    diagnostic envelope.
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

- Atomic UI-based setup for an HVAC equipment group and first zone, with one or
  more existing Home Assistant `climate` thermostats.
- Single-system, independent-thermostat, and shared/zoned equipment
  relationships, including explicit thermostat membership for every zone.
- Native parent and zone reconfigure flows plus safe runtime options.
- One read-only virtual `climate` entity for every configured zone.
- Effective temperature, optional humidity, optional temperature spread,
  valid-source count, operating-mode, relationship, capability, and latest
  activity sensors.
- Configuration, source, thermostat, and reconciliation health binary sensors,
  plus a configuration-only observation-enabled switch for each zone.
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
- Home Assistant Repairs notifications for actionable observation and safety
  failures.
- A bounded material activity history, one diagnostic activity Event entity
  for the equipment group and each zone, and one diagnostic Latest Activity
  sensor per zone.
- A privacy-bounded `intelligent_climate_activity` event for automations.
- Debounced, atomic persistence of nonauthoritative activity history and current
  restart baselines.

The original thermostat remains independently available and is the only
supported way to change HVAC settings.

## What it deliberately does not do

Phase 1 does not provide:

- Thermostat, fan, switch, humidity, ventilation, or other equipment control.
- Schedules, manual overrides, occupancy control, or window suspension.
- Predictive control, adaptive start or stop, thermal models, or simulation.
- Equipment arbitration, heat-pump optimization, or auxiliary-heat logic.
- Predictive, model, schedule, override, fan-control, or simulation entities.
- A custom frontend or activity panel beyond the Home Assistant entity,
  Logbook, event-bus, and diagnostics surfaces.
- Automatic repair actions or a configuration-changing Repairs flow.

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
2. One or more existing thermostat entities from the `climate` domain.
3. For multiple thermostats, whether they are independent or share/zoned
   equipment.
4. A first-zone display name, thermostat membership, and one or more existing
   temperature sources.

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
reconfigure action to change its name, thermostat membership, temperature
sources, and each retained source's offset, weight, priority, and enabled
state. Use the parent reconfigure action to change the equipment-group name,
equipment type, thermostat membership, or relationship.

Zone and source identities are generated once and remain stable when display
names change. Retained source bindings preserve their calibration, weight,
priority, enabled state, and source identity.

The options flow changes observation enablement, aggregation, freshness,
plausibility, outlier, minimum-source, and bounded-history settings without
manual YAML or Store edits. In shared/zoned groups it also maintains the
configured zone-priority order; this is descriptive in Phase 1 and never
arbitrates physical commands.

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

The Intelligent Climate-owned `data` section uses diagnostics schema version 1
and includes:

- Integration and config-entry schema versions.
- Configuration lifecycle state.
- Equipment-group and zone structure.
- Safe observation options.
- Thermostat availability, capability status, and approved observed values.
- Zone aggregation status and effective values.
- Configured-order source rows, quality counts, exclusion-reason counts, and
  safe report timestamps.
- A sorted list of active Intelligent Climate Repairs issue codes.
- Bounded material activity history, configured history limits, and current
  Store load/dirty/write-health status.

Schema version 1 permits backward-compatible additive fields such as the
Repairs summary. Every download uses a new random secret salt. Entity
references and user-assigned names in the Intelligent Climate data section
become report-scoped HMAC-SHA256 pseudonyms, so those pseudonyms change between
downloads. The integration-owned data section omits the raw config-entry ID and
unique ID, raw entity IDs, raw user-assigned names, Home Assistant `State`
objects and arbitrary attributes, credentials, coordinates, URLs, and
filesystem paths.

Integration-generated equipment-group, zone, and source UUIDs remain stable.
They can therefore correlate multiple reports produced from the same
configuration even though entity and name pseudonyms change.

Home Assistant adds an outer diagnostic envelope that Intelligent Climate does
not own and cannot redact. Depending on the Home Assistant release, that
wrapper and the downloaded filename may include:

- The raw config-entry ID, including in the diagnostic filename.
- Home Assistant version and platform/system information.
- Time zone.
- Installed custom-integration names and versions.
- Integration documentation URLs.
- Other general diagnostic metadata controlled by Home Assistant.

Diagnostics reduce accidental disclosure; they do not make the complete
download safe for every public context. **Review the filename and the entire
downloaded file, including Home Assistant's outer envelope, before posting it
publicly.**

## Repairs notifications

Actionable Intelligent Climate failures appear under **Settings > System >
Repairs** in Home Assistant. Task 13 reports these entry-scoped conditions:

- The equipment group has no configured zones after its final zone is removed.
- A configured thermostat or enabled source is missing after startup
  reconciliation.
- An existing source is definitively incompatible with its configured binding.
- Persisted configuration or runtime Store data cannot be migrated or
  validated safely.
- Runtime persistence reports at least three consecutive write failures.
- The observation-only command boundary blocks an unexpected physical-command
  intent.

The no-zone issue clears after a zone is added. Missing and incompatible entity
issues clear after the configured references recover. Configuration migration
issues clear after a later valid migration;
Store validation/quarantine issues clear only after a clean replacement save.
Store-write issues clear after a successful save, and command-boundary issues
clear during a later clean setup. The command boundary suppresses the intent
and does not command equipment.

There is no automatic Repairs flow, and Repairs never changes configuration.
Task 14 wires the Store-write issue to the bounded runtime Store: the issue
appears after three consecutive save failures and clears after a successful
save. Continue using the original thermostat for all physical HVAC control.

## Activity history and events

Intelligent Climate records only material observation activity. It does not
record every source report, watchdog evaluation, snapshot revision, or
timestamp refresh. The bounded history covers lifecycle and runtime-state
transitions, source exclusion/recovery, observed thermostat mode or target
changes, material capability changes, Repairs transitions, rejected control
attempts, and Store failure/recovery.

Home Assistant exposes this activity through:

- One diagnostic Activity Event entity on the equipment-group device.
- One diagnostic Activity Event entity on each zone device.
- One diagnostic Latest Activity sensor on each zone device.
- The `intelligent_climate_activity` event for automations.
- The normal Recorder/Logbook state history of the Event entities.

The event-bus payload contains the config-entry ID, generated group and optional
zone UUIDs, activity type, stable reason code, severity, timestamp, and concise
explanation. It does not contain the internal detail projection, entity IDs,
user-assigned names, source values, Home Assistant State objects, contexts,
command payloads, exception text, URLs, or paths.

Activity is retained oldest-to-newest for the configured age and count limits,
with an absolute maximum of 500 records. Store writes are debounced for 30
seconds and forced within five minutes while dirty. A clean unload or Home
Assistant core shutdown attempts a final save for at most five seconds;
persistence failure never changes or blocks physical equipment.

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

### Activity is not added for every source report

That is expected. Equivalent source reports, unchanged watchdog evaluations,
timestamp-only capability rediscovery, and snapshot revision changes are not
material activity. Check the Activity Event entity or Latest Activity sensor
after a real source exclusion/recovery, thermostat mode/target change, or other
documented transition.

### A runtime-data save issue appears in Repairs

Home Assistant could not persist the nonauthoritative activity history at least
three consecutive times. In-memory observation can continue safely. Check
storage availability and Home Assistant logs; a later successful save clears
the issue automatically. Exception text and filesystem paths are not copied
into activity, diagnostics, or the integration's Repairs data.

### A migration or runtime-data validation issue appears

Intelligent Climate rejected persisted configuration or Store data that could
not be interpreted safely. Config-entry migration leaves the complete graph
unchanged when validation fails. Semantically invalid Store data is retained
in one bounded quarantine until a clean replacement save succeeds; unsupported
future Store data is preserved read-only. Live observation starts from current
Home Assistant states whenever that is safe, and no persisted temperature is
substituted.

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

Runtime Store data is local and nonauthoritative. Bounded activity history is
restored into its existing diagnostic surfaces. Strictly validated source
baselines may seed source-quality comparison during live restart
reconciliation, but they are not observations and never become public climate
state. Persisted zone temperatures are never hydrated into the coordinator or
public entities. A missing, quarantined, unsupported, or unreadable Store
starts with live reconciliation and no restored public temperature.

## Current roadmap and Phase 1 status

Phase 1 was delivered in small observation-only slices. Tasks 1 through 16 are
implemented: repository and schema foundations, UI configuration, zone
identity, entity validation, capability discovery, source normalization and
health, aggregation, the event-driven coordinator, read-only zone climate
entities, redacted diagnostics, Repairs notifications, and bounded activity
history/events with Store v1 persistence, migration, quarantine, and lifecycle
recovery hardening. Automated acceptance evidence is complete; final Phase 1
acceptance is pending the documented Home Assistant UI walkthrough for the
0.0.8 candidate.

Scheduled control begins no earlier than Phase 2, and predictive control
remains a later phase.

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
ownership fail closed. Release 0.0.6 transactionally migrates config entries
from `1.0` to `1.1` after validating the complete parent/options/zone graph.
Runtime Store major version 1 and inner schema version 1 remain unchanged; the
Home Assistant Store envelope migrates from minor 1 to minor 2. The existing
`decisions` array contains strict activity records and `command_journal`
remains empty.

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

Strictly validated Store baselines are comparison-only inputs during this live
reconciliation. Saved zone observations are never loaded into the coordinator
or virtual climate entities. Invalid Store data is quarantined; future or
unreadable envelopes remain preserved read-only.

Material activity flows through one bounded entry-scoped history. Each new
record fires one `intelligent_climate_activity` bus event and updates only the
matching Activity Event/Latest Activity surfaces. Runtime Store writes use Home
Assistant Store version 1, key `intelligent_climate.<entry_id>`, atomic writes,
a 30-second debounce, a five-minute maximum dirty interval, bounded retry, and
a five-second unload/core-shutdown limit.

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
configuration, the current immutable coordinator snapshot, and bounded active
Repairs codes, activity, and Store health.

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

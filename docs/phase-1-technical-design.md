# Intelligent Climate

## Phase 1 Technical Design: Foundation and Observation

**Domain:** `intelligent_climate`  
**Status:** Implementation baseline  
**Target:** Home Assistant 2026.7  
**Minimum supported release:** Home Assistant Core 2026.7.0  
**Validated deployment profile:** Home Assistant OS 18.1, Core 2026.7.2, Python 3.14.6, aarch64  
**Predictive control:** Explicitly excluded from Phase 1

---

## 1. Purpose and outcome

Phase 1 establishes a production-quality, HACS-installable Home Assistant integration that can be configured entirely through the Home Assistant interface, represent HVAC equipment and climate zones, observe real entities, calculate trustworthy zone conditions, expose a useful virtual climate surface, preserve a bounded activity history, diagnose configuration and source-data problems, and restart safely.

Phase 1 does **not** control physical HVAC equipment. It does not implement schedules, manual overrides, window suspension, occupancy mode changes, thermal learning, adaptive start or stop, predictive control, equipment arbitration, fan control, or simulation. The data contracts and module boundaries anticipate those features, but no future mode can be selected and no predictive result can enter the Phase 1 decision path.

This scope resolves an important tension in the master specification: the complete project must eventually satisfy the full nonnegotiable requirements, while the published phased plan assigns active scheduled control to Phase 2 and predictive control to Phase 4. Phase 1 therefore delivers a safe observation foundation and makes all deferred behavior explicit rather than partially implementing it.

### 1.1 Phase 1 safety invariant

> For every event, configuration, restart condition, entity state, and user interaction, Phase 1 emits zero Home Assistant service calls that can change a real thermostat, fan, humidifier, dehumidifier, ventilation device, or other physical climate equipment.

The invariant is enforced structurally. All decisions pass through a `CommandSink` interface; the only Phase 1 implementation is `ObserveOnlyCommandSink`, which records a suppressed intent and cannot call `hass.services.async_call`.

### 1.2 Governing inputs

This design is based on these project sources, in precedence order:

1. `nonnegotiable-requirements.txt`
2. `architecture-decisions.txt`
3. Phase 1 boundaries in `Master-specifications.txt`
4. Remaining requirements in `Master-specifications.txt`
5. The supplied redacted Google Nest diagnostic fixture

The latest stable Home Assistant Core release at design time is 2026.7.2. The integration targets the 2026.7 API family and declares 2026.7.0 as its minimum supported release. Release status was verified against the official Home Assistant Core release list: <https://github.com/home-assistant/core/releases>.

## 2. Scope

### 2.1 Included

- HACS-compatible custom integration packaging.
- UI-only initial configuration, options, and reconfiguration.
- One config entry per HVAC equipment group.
- One or more zones per equipment group.
- Selection and validation of thermostats and climate-related source entities.
- Stable equipment-group and zone identifiers.
- Runtime thermostat capability discovery.
- Event-driven source observation.
- Temperature and humidity normalization, calibration, health evaluation, outlier rejection, and aggregation.
- Read-only virtual climate entity for each zone.
- Phase 1 operational, health, and activity entities.
- Disabled and Observe-only modes.
- Safe startup reconciliation, unloading, and reloading.
- Versioned, bounded runtime persistence.
- Redacted diagnostics.
- Home Assistant Repairs issues for actionable configuration failures.
- Normal integration logging, structured decision records, Home Assistant events, Event entities, and Logbook-visible activity.
- Automated tests, static analysis, and CI quality gates.

### 2.2 Deferred

The following are designed as extension points but are not implemented or user-selectable in Phase 1:

- Scheduled control and the schedule editor: Phase 2.
- Manual override detection and expiration: Phase 2.
- Window/door suspension and occupancy behavior: Phase 2.
- Safety-limit enforcement through active commands: Phase 2.
- Fan and humidity control: Phase 2 and later.
- Thermal observation datasets and fitted models: Phase 3.
- Shadow predictions: Phase 3.
- Adaptive start, adaptive stop, and predictive control: Phase 4.
- Shared-equipment command arbitration and heat-pump intelligence: Phase 5.
- Full simulation and advanced frontend: Phase 7.

Phase 1 may store entity bindings and equipment metadata needed by later phases. It may report those entities' availability. It must not claim that deferred behaviors are active.

## 3. Architectural decisions

### AD-001: One config entry per equipment group

An equipment group is the lifecycle and command-ownership boundary. Independent systems use separate entries. Thermostats that share equipment are placed in one entry. A thermostat entity may belong to only one Intelligent Climate config entry.

This supports multiple independent or related thermostats without creating competing controllers. It also permits one entry to unload or fail without affecting another system.

### AD-002: Zones are config subentries and child devices

Each zone is a Home Assistant config subentry of type `zone`, has an immutable `zone_id`, and owns a Home Assistant zone device. The device is linked to the equipment-group device with `via_device`, and zone entities belong to the zone subentry/device. Adding, renaming, reconfiguring, or removing a zone uses the supported config-subentry UI lifecycle and does not create another top-level integration entry.

### AD-003: Required configuration stays in entry and subentry data

Required equipment configuration is stored in parent `ConfigEntry.data`; required zone configuration is stored in each zone `ConfigSubentry.data`. Parent and zone reconfigure flows change those documents. Runtime preferences are stored in parent `ConfigEntry.options`. Users never edit YAML or `.storage` files. This follows the Home Assistant 2026.7 distinction between required setup data and optional behavior.

### AD-004: Runtime state uses a separate versioned Store

Restart reconciliation data, source-health state, the last decision, and bounded activity history are stored in `.storage/intelligent_climate.<entry_id>`. This data is not authoritative configuration and can be rebuilt safely if lost.

### AD-005: Event-driven coordinator with pure delegates

The coordinator subscribes to state and registry changes and schedules targeted reevaluation. It does not contain the domain algorithms. Capability discovery, source validation, aggregation, state transitions, decision construction, diagnostics, and persistence are separate typed modules with pure functions where possible.

### AD-006: No active command adapter in Phase 1

The physical-command interface exists so Phase 2 can be implemented without rewriting the coordinator. Phase 1 dependency injection can construct only `ObserveOnlyCommandSink`. Importing or instantiating an active sink is blocked by tests and package structure.

### AD-007: Conservative truthfulness

Missing data is represented as missing or degraded. The integration does not infer HVAC stages, auxiliary heat, energy use, weather, or equipment performance unless those values are directly available. Derived values are named and labeled as calculated.

## 4. Runtime architecture

### 4.1 Component relationships

| Component | Responsibility | May cause physical control? |
|---|---|---:|
| Config flow and options flow | Build and validate the equipment/zone graph | No |
| Config repository | Convert config-entry JSON into immutable typed models | No |
| Entry runtime | Own the entry-scoped services and lifecycle | No |
| Coordinator | Subscribe, debounce, reconcile, evaluate, and dispatch updates | No |
| Capability resolver | Normalize thermostat capabilities from supported HA APIs | No |
| Observation pipeline | Normalize source states and determine health | No |
| Aggregation engine | Calculate effective temperature/humidity and spread | No |
| Control state machine | Select Disabled, Observing, or Degraded runtime state | No |
| Decision engine | Produce an explanation and optional proposed intent | No |
| `ObserveOnlyCommandSink` | Persist a suppressed intent; reject execution | **No by construction** |
| History manager | Maintain bounded in-memory and persisted activity records | No |
| Entity adapters | Present coordinator snapshots to Home Assistant | No |
| Diagnostics and Repairs | Report redacted state and actionable problems | No |

### 4.2 Entry runtime object

`IntelligentClimateRuntime` is stored at `hass.data[DOMAIN][entry.entry_id]` and contains only entry-scoped objects:

```text
IntelligentClimateRuntime
  config: EquipmentGroupConfig
  coordinator: IntelligentClimateCoordinator
  capabilities: dict[entity_id, ThermostatCapabilities]
  history: ActivityHistory
  store: RuntimeStore
  command_sink: ObserveOnlyCommandSink
  issue_manager: IssueManager
  unsubscribe_callbacks: list[Callable[[], None]]
```

No global mutable singleton holds zone state. Domain-level data contains only the entry runtime mapping and service-registration reference count.

### 4.3 Data flow

1. A tracked entity or registry event arrives.
2. The coordinator marks only affected zones dirty.
3. Events within 250 ms are coalesced into one evaluation batch.
4. The observation pipeline reads the current Home Assistant states and returns normalized source observations.
5. The aggregation engine creates one immutable `ZoneObservation` per dirty zone.
6. The control state machine determines the zone runtime state.
7. The decision engine creates a `DecisionRecord` with a stable reason code and human-readable explanation.
8. The no-op command sink records any proposed intent as suppressed.
9. The coordinator publishes one `CoordinatorSnapshot`, signals entity updates, emits important activity, and schedules a debounced store save.

No polling loop is required. A 60-second watchdog reevaluation is scheduled only when a freshness deadline, startup guard deadline, or recovery confirmation deadline is pending.

## 5. Repository structure

```text
intelligent-climate/
├── README.md
├── LICENSE
├── hacs.json
├── pyproject.toml
├── requirements_test.txt
├── .strict-typing-filter
├── .github/
│   └── workflows/
│       ├── tests.yml
│       ├── hassfest.yml
│       └── hacs.yml
├── custom_components/
│   └── intelligent_climate/
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── config_flow.py
│       ├── zone_flow.py
│       ├── options_flow.py
│       ├── coordinator.py
│       ├── runtime.py
│       ├── capability.py
│       ├── entity.py
│       ├── climate.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       ├── event.py
│       ├── diagnostics.py
│       ├── repairs.py
│       ├── storage.py
│       ├── history.py
│       ├── services.yaml
│       ├── quality_scale.yaml
│       ├── translations/
│       │   └── en.json
│       ├── models/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── equipment.py
│       │   ├── zone.py
│       │   ├── observation.py
│       │   ├── decision.py
│       │   └── persistence.py
│       ├── observation/
│       │   ├── __init__.py
│       │   ├── normalize.py
│       │   ├── health.py
│       │   ├── outliers.py
│       │   └── aggregate.py
│       ├── control/
│       │   ├── __init__.py
│       │   ├── state_machine.py
│       │   ├── decision_engine.py
│       │   ├── command_sink.py
│       │   └── reasons.py
│       └── util/
│           ├── temperature.py
│           ├── identifiers.py
│           ├── redact.py
│           └── time.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── nest_cool_idle.json
│   │   └── storage_v1.json
│   ├── unit/
│   │   ├── test_capability.py
│   │   ├── test_normalize.py
│   │   ├── test_health.py
│   │   ├── test_outliers.py
│   │   ├── test_aggregate.py
│   │   ├── test_state_machine.py
│   │   └── test_storage_models.py
│   ├── integration/
│   │   ├── test_config_flow.py
│   │   ├── test_options_flow.py
│   │   ├── test_reconfigure.py
│   │   ├── test_setup_unload_reload.py
│   │   ├── test_entities.py
│   │   ├── test_observation_pipeline.py
│   │   ├── test_restart_reconciliation.py
│   │   ├── test_registry_changes.py
│   │   ├── test_diagnostics.py
│   │   ├── test_repairs.py
│   │   └── test_no_physical_commands.py
│   └── snapshots/
├── docs/
│   ├── phase-1-technical-design.md
│   ├── configuration.md
│   ├── entities.md
│   ├── diagnostics.md
│   └── development.md
└── frontend/
    └── README.md
```

`frontend/` is deliberately separate and contains no Phase 1 runtime dependency. It reserves the eventual companion card/package boundary.

## 6. Config-entry architecture

### 6.1 Config-entry identity and versioning

- `entry.version = 1`
- `entry.minor_version = 0`
- `unique_id = equipment_group_id`, a generated UUIDv4 stored as a lowercase string.
- Title defaults to the user-supplied equipment-group name.
- Duplicate protection is based on selected thermostat entity ownership, not the display name.

Each zone subentry has `subentry_type = "zone"`, `unique_id = zone_id`, and its own data version field. Entry/subentry migrations are transactional: validate the complete migrated parent-and-zone graph in memory, update it once, then set the new version. If migration cannot preserve meaning, setup stops, a Repairs issue is created, and no entities or listeners are installed.

### 6.2 Authoritative parent config-entry data

```json
{
  "equipment_group": {
    "equipment_group_id": "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3",
    "name": "Main Floor HVAC",
    "equipment_type": "air_source_heat_pump",
    "relationship": "single_system",
    "thermostats": [
      {
        "entity_id": "climate.dining_room",
        "role": "primary"
      }
    ],
    "shared_policy": null
  }
}
```

### 6.3 Authoritative zone subentry data

```json
{
  "data_version": 1,
  "zone_id": "99246285-6f02-4e8a-94ed-bdfd4a5e62c4",
  "name": "Dining Room",
  "thermostat_entity_ids": ["climate.dining_room"],
  "temperature_sources": [
    {
      "source_id": "f15f73b1-ea59-4b28-819f-7b99acf065bf",
      "entity_id": "climate.dining_room",
      "attribute": "current_temperature",
      "offset_c": 0.0,
      "weight": 1.0,
      "priority": 0
    }
  ],
  "humidity_sources": [
    {
      "source_id": "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
      "entity_id": "climate.dining_room",
      "attribute": "current_humidity",
      "offset_pct": 0.0,
      "weight": 1.0,
      "priority": 0
    }
  ],
  "window_door_entity_ids": [],
  "occupancy_entity_ids": [],
  "stage_entity_ids": [],
  "fan_entity_ids": []
}
```

Entity IDs are configuration references, while stable integration unique IDs use immutable equipment and zone UUIDs. Entity-registry rename events update the owning parent entry or zone subentry through supported Home Assistant update APIs and then reload the parent entry.

### 6.4 Config-entry options

Options contain tunable observation behavior that can be changed without changing the zone graph:

```json
{
  "observation_enabled": true,
  "temperature_strategy": "median",
  "humidity_strategy": "median",
  "min_valid_temperature_sources": 1,
  "min_valid_humidity_sources": 1,
  "source_stale_after_seconds": 1800,
  "startup_reconciliation_seconds": 60,
  "jump_limit_c_per_5_minutes": 2.8,
  "outlier_floor_c": 1.7,
  "indoor_temperature_min_c": 1.7,
  "indoor_temperature_max_c": 43.3,
  "history_max_records": 500,
  "history_max_age_days": 30,
  "log_level_detail": "normal"
}
```

Defaults correspond approximately to 30-minute freshness, 5°F per five-minute jump rejection, a 3°F outlier floor, and a plausible indoor range of 35-110°F. The UI displays values in the Home Assistant unit system; storage uses Celsius.

### 6.5 Initial config flow

| Step | Required input and validation |
|---|---|
| `user` | Equipment-group name and type. Name must be nonblank. |
| `thermostats` | Select one or more `climate` entities. Each must exist and must not be owned by another Intelligent Climate entry. |
| `relationship` | Single system, independent thermostats in one physical group, or shared/zoned equipment. More than one thermostat requires an explicit selection. |
| `zone` | First-zone name, thermostat membership, and at least one temperature source. IDs and names must be unique within the pending entry. |
| `zone_sources` | Optional humidity, window/door, occupancy, stage, and fan entities; calibration, weights, and priority. Domain/device-class compatibility is validated. |
| `observation` | Aggregation strategy, minimum valid sources, freshness, jump, and outlier settings. |
| `confirm` | Human-readable relationship summary and an explicit statement that Phase 1 cannot control equipment. |

The flow validates the parent equipment and first zone before creating anything. It creates the parent entry, then uses Home Assistant's supported `async_on_create_entry()` hook to create the first zone subentry after the parent exists. Canceling before confirmation leaves no parent, subentry, or Store data. Additional zones are added with the zone subentry flow from the integration entry page.

### 6.6 Options flow

The options menu provides:

- Enable or disable observation.
- Change aggregation and source-health thresholds.
- Change activity-history limits.
- Review discovered thermostat capabilities.

Zone sources, calibration, name, and thermostat membership are required zone setup, so they are changed through the zone subentry's reconfigure flow rather than the options flow.

### 6.7 Parent and zone reconfigure flows

The parent reconfigure flow changes equipment-defining inputs:

- Equipment-group name or type.
- Thermostat membership.
- Single/shared relationship.
- Shared-equipment metadata and future arbitration policy.

It validates the proposed graph before committing. Removed thermostats are unsubscribed on reload. Added thermostats are capability-checked. A thermostat already owned by another entry is rejected with a translatable error.

The zone subentry flow supports adding and reconfiguring a zone. It changes the zone name, thermostat membership, source bindings, calibration, weights, and priority. Zone removal uses Home Assistant's native subentry removal UI and its confirmation. If the final zone is removed, the parent entry remains safely loaded without zone entities and raises a `no_zones_configured` Repairs issue that directs the user to add a zone or remove the equipment-group entry.

### 6.8 Setup, reload, and unload

Setup order is fixed:

1. Parse and validate the parent entry and all zone subentries as one graph.
2. Load and migrate runtime Store.
3. Build capability snapshots.
4. Construct the no-op command sink.
5. Register listeners.
6. Enter Reconciliation.
7. Forward entity platforms.
8. Publish the first snapshot only after all configured sources have been examined.

Startup validation distinguishes persisted structure from interactive entity
selection. Persisted parent thermostat references must have concrete valid
entity IDs, use the `climate` domain, describe exactly one primary thermostat
for the supported single-system relationship, have no shared policy, remain
exclusively owned across Intelligent Climate entries, and match every zone
binding. Persisted temperature sources must have concrete valid entity IDs,
use only `climate.current_temperature` or a `sensor` state binding, contain no
duplicate `(entity_id, attribute)` pair, and retain unique source IDs across
the entry. All schema and graph invariants remain fail-closed.

Persisted startup validation does not require referenced entities to have
created a current Home Assistant `State`, and it does not inspect a live sensor
device class. A referenced entity may be absent, unavailable, unknown,
disabled, restoring, or not yet loaded without making the config entry
malformed. The initial coordinator snapshot represents missing temperature
sources as `SourceQuality.UNAVAILABLE` and missing thermostats as unavailable
normalized climate states. The climate platform still starts and creates the
zone entity, which remains unavailable until its current observation satisfies
the normal availability rules.

The coordinator registers state-change and state-report subscriptions for the
persisted entity IDs even when no current state exists. When a source or
thermostat appears, the existing targeted debounce path reevaluates the
affected zone and can make the read-only climate entity available without an
entry reload, config-flow edit, or polling. Interactive initial thermostat,
zone-add, and zone-reconfigure selections remain strict live checks: selected
entities must exist, domains must match, and sensor sources must currently
advertise the temperature device class. This startup recovery path remains
observation-only and cannot issue physical HVAC commands.

Unload order is the reverse. Timers are canceled, listeners removed, a bounded final store write is attempted, platforms unload, and the runtime object is removed. Unload never changes a physical thermostat.

## 7. Domain data models

All internal models are strict, immutable `dataclass(frozen=True, slots=True)` values or `StrEnum` values. Config-entry and Store JSON are decoded at the boundary; untyped dictionaries do not flow through the decision engine.

### 7.1 Equipment group

```text
EquipmentGroupConfig
  equipment_group_id: UUID
  name: str
  equipment_type: EquipmentType
  relationship: EquipmentRelationship
  thermostats: tuple[ThermostatBinding, ...]
  shared_policy: SharedEquipmentPolicy | None
```

`EquipmentType` includes conventional, air-source heat pump, heat pump with auxiliary electric heat, dual fuel, boiler, radiant, mini-split, multistage, variable capacity, fan coil, and unknown. Phase 1 records the value but does not vary decisions by equipment type.

`EquipmentRelationship` is `SINGLE_SYSTEM`, `INDEPENDENT`, or `SHARED_ZONED`. When `SHARED_ZONED` is selected, a future-safe `SharedEquipmentPolicy` must identify zone priority order and conflict policy. Phase 1 validates and reports it but does not arbitrate commands.

### 7.2 Thermostat binding and capabilities

```text
ThermostatBinding
  entity_id: str
  role: PRIMARY | SECONDARY

ThermostatCapabilities
  entity_id: str
  hvac_modes: frozenset[HVACMode]
  supported_features: ClimateEntityFeature
  target_temperature: bool
  target_temperature_range: bool
  fan_modes: tuple[str, ...]
  preset_modes: tuple[str, ...]
  current_temperature_available: bool
  current_humidity_available: bool
  auxiliary_heat_observable: bool
  stage_observable: bool
  discovered_at: datetime
```

Capabilities come only from public Home Assistant state attributes and feature flags. Phase 1 never treats a vendor trait as universally available. Missing stage or auxiliary-heat data is reported as `not_observable`, never `off`.

### 7.3 Zone

```text
ZoneConfig
  zone_id: UUID
  name: str
  thermostat_entity_ids: tuple[str, ...]
  temperature_sources: tuple[TemperatureSource, ...]
  humidity_sources: tuple[HumiditySource, ...]
  window_door_entity_ids: tuple[str, ...]
  occupancy_entity_ids: tuple[str, ...]
  stage_entity_ids: tuple[str, ...]
  fan_entity_ids: tuple[str, ...]

TemperatureSource
  source_id: str
  entity_id: str
  attribute: str | None
  offset_c: float
  weight: float
  priority: int
  enabled: bool

HumiditySource
  source_id: str
  entity_id: str
  attribute: str | None
  offset_pct: float
  weight: float
  priority: int
  enabled: bool
```

`source_id` is a stable UUID and does not change when an entity is renamed. A source can read the entity state or a supported attribute such as a thermostat's `current_temperature`.

### 7.4 Source observation and health

```text
SourceObservation[T]
  source_id: str
  raw_value: object
  normalized_value: T | None
  observed_at: datetime
  source_last_reported: datetime | None
  quality: SourceQuality
  exclusion_reason: ExclusionReason | None
  restored: bool

SourceQuality
  VALID
  UNAVAILABLE
  UNKNOWN
  NON_NUMERIC
  NON_FINITE
  UNIT_UNSUPPORTED
  IMPLAUSIBLE
  STALE
  RESTORED_NOT_CONFIRMED
  JUMP_REJECTED
  OUTLIER
  CONTRADICTORY
```

The full set of included and excluded sources, with reasons, is retained in the coordinator snapshot and exposed through diagnostics. It is not copied into high-frequency entity attributes.

Source age is calculated from Home Assistant's `State.last_reported`, not
`State.last_updated`. State-change and state-report events both trigger the
same coalesced affected-zone evaluation, so an unchanged but recently reported
reading remains fresh while a genuinely unreported source can still become
stale.

### 7.5 Zone observation

```text
ZoneObservation
  zone_id: UUID
  effective_temperature_c: float | None
  effective_humidity_pct: float | None
  temperature_spread_c: float | None
  valid_temperature_source_ids: tuple[str, ...]
  valid_humidity_source_ids: tuple[str, ...]
  excluded_sources: tuple[SourceExclusion, ...]
  thermostat_states: tuple[NormalizedClimateState, ...]
  sensor_data_degraded: bool
  thermostat_data_degraded: bool
  calculated_at: datetime
```

### 7.6 Normalized climate state

```text
NormalizedClimateState
  entity_id: str
  available: bool
  hvac_mode: HVACMode | None
  hvac_action: HVACAction | None
  current_temperature_c: float | None
  target_temperature_c: float | None
  target_low_c: float | None
  target_high_c: float | None
  current_humidity_pct: float | None
  fan_mode: str | None
  preset_mode: str | None
  auxiliary_heat_state: TRUE | FALSE | NOT_OBSERVABLE
  context_id: str | None
  last_changed: datetime
  last_updated: datetime
```

### 7.7 Decision and proposed intent

```text
DecisionRecord
  decision_id: UUID
  timestamp: datetime
  equipment_group_id: UUID
  zone_id: UUID
  previous_state: ControlState
  new_state: ControlState
  trigger: TriggerType
  reason_code: DecisionReason
  input_summary: RedactedInputSummary
  proposed_intent: ProposedIntent | None
  command_status: NONE | SUPPRESSED_OBSERVE_ONLY
  confidence: None
  explanation: str

ProposedIntent
  intent_type: NONE
  target_entity_id: None
  parameters: empty mapping
```

In Phase 1 `confidence` is always `None`; model confidence does not exist yet. `ProposedIntent.intent_type` can only be `NONE`. This prevents an observation explanation from being mistaken for a control recommendation.

## 8. Zone and equipment relationship model

### 8.1 Cardinality and ownership

| Relationship | Rule |
|---|---|
| Config entry to equipment group | Exactly 1:1 |
| Config entry to zone subentry | 1:N |
| Equipment group to thermostat | 1:N |
| Equipment group to zone | 1:N |
| Zone to thermostat | 1:N, limited to thermostats in its equipment group |
| Thermostat to zone within a group | 1:N; shared sensing/control topology is allowed |
| Thermostat to config entry | Exactly 0:1; duplicate ownership is forbidden |
| Zone to temperature source | 1:N; at least one is required |
| Source entity to zone | N:M; a room sensor may contribute to more than one logical zone |
| Zone to Home Assistant device | Exactly 1:1 |

### 8.2 Relationship validation

- Every zone references at least one group thermostat.
- Every zone has at least one temperature source.
- Every source ID is unique within the entry.
- Every selected thermostat is assigned to at least one zone.
- A single thermostat may serve several zones only inside one equipment group.
- A `SHARED_ZONED` group with multiple zones requires unique positive priority values and an explicit future conflict policy.
- A source selected twice in one zone with the same entity and attribute is rejected as a duplicate.
- A source may be shared across zones, but the confirmation screen calls this out.

### 8.3 Device registry

The equipment-group device identifier is `(DOMAIN, equipment_group_id)`. Each zone device identifier is `(DOMAIN, zone_id)`, is linked to its `config_subentry_id`, and uses the group device as `via_device`.

The integration does not claim or merge the physical thermostat's existing device. Zone devices list the selected thermostat entity IDs in diagnostic information, while the Home Assistant device relationship remains noninvasive.

## 9. Observation and aggregation rules

### 9.1 Processing order

For each source, Phase 1 performs the following in order:

1. Confirm the entity and configured attribute exist.
2. Reject `unknown`, `unavailable`, nonnumeric, nonfinite, or unsupported-unit values.
3. Convert temperatures to Celsius.
4. Apply the configured calibration offset.
5. Reject values outside the configured plausible range.
6. Reject a restored value until a live update confirms it after startup.
7. Reject a value whose source age exceeds the configured freshness limit.
8. Reject an instantaneous jump beyond the configured rate limit unless a second reading at least 30 seconds later confirms the new range.
9. Apply cross-source outlier rules.
10. Enforce the minimum-valid-source count.
11. Calculate the configured aggregate and round the published temperature to 0.1°C internally before Home Assistant unit conversion.

### 9.2 Cross-source outlier rules

- With three or more otherwise valid sources, calculate the median and median absolute deviation (MAD). Reject a source when its absolute deviation exceeds `max(outlier_floor_c, 3 × 1.4826 × MAD)`. When MAD is zero, use `outlier_floor_c`.
- With two valid sources, retain both when their spread is at or below `2 × outlier_floor_c`. If it is greater, mark both contradictory. Use the configured priority source only if one exists; otherwise publish no effective temperature and enter Degraded.
- With one valid source, use it only when the zone's minimum-valid count is one.
- Weighted-average sources must have finite weights greater than zero. Weights are normalized at evaluation time.

Supported Phase 1 temperature strategies are mean, median, weighted average, and priority. Humidity supports mean, median, weighted average, and priority. Occupied-room, warmest-room, and coldest-room strategies are deferred because they require Phase 2 occupancy/control semantics.

### 9.3 Restart/reboot value handling

A state carrying Home Assistant's restored-state marker is not accepted as live input. The integration waits for a post-start source update. During the 60-second reconciliation window it evaluates but publishes the zone as reconciling/degraded rather than using a suspicious reboot value. A large post-restart jump must receive a second confirming reading before inclusion.

This directly prevents a transient value such as 0°F from producing an extreme calculated zone temperature. Because Phase 1 cannot issue commands, it also cannot turn that bad value into a physical control action.

## 10. Coordinator responsibilities

### 10.1 The coordinator must

- Own entry-scoped subscriptions and timers.
- Track the source-to-zone dependency index.
- Coalesce state bursts and reevaluate only affected zones.
- Rebuild capability snapshots when thermostat features change.
- Reconcile persisted observations with live Home Assistant state after startup.
- Invoke source normalization, health checks, outlier rejection, and aggregation.
- Invoke the control state machine and decision engine.
- Pass all intents to the injected command sink.
- Maintain a single immutable entry snapshot.
- Notify entity platforms through coordinator listeners.
- Create bounded activity records and emit material activity events.
- Debounce noncritical Store writes.
- Create and clear Repairs issues through the issue manager.
- Cancel every callback and timer during unload.

### 10.2 The coordinator must not

- Contain entity-platform rendering logic.
- Parse config-entry dictionaries throughout runtime code.
- Fit or evaluate a thermal model.
- calculate predictions, confidence, or adaptive start.
- Resolve shared-equipment demand conflicts.
- Call Home Assistant climate, fan, humidifier, or switch services.
- Write Store data on every state change.
- expose source entity IDs in normal logs at `INFO` level.
- Keep unbounded observations or decisions in memory or storage.

### 10.3 Triggers

`TriggerType` in Phase 1 is one of:

- `STARTUP`
- `RECONCILIATION_COMPLETE`
- `SOURCE_STATE_CHANGED`
- `THERMOSTAT_STATE_CHANGED`
- `ENTITY_REGISTRY_CHANGED`
- `DEVICE_REGISTRY_CHANGED`
- `OPTIONS_CHANGED`
- `WATCHDOG_DEADLINE`
- `USER_ENABLED`
- `USER_DISABLED`
- `RELOAD`
- `UNLOAD`

Each decision records one primary trigger and optional counts of coalesced triggers.

## 11. Phase 1 entity matrix

Entity unique IDs are stable and use `<zone_id>:<entity_key>` or `<equipment_group_id>:<entity_key>`. Display names may change without changing unique IDs.

### 11.1 Zone entities

| Platform / key | Default | Category | State and purpose |
|---|---:|---|---|
| `climate.zone` | Enabled | None | Read-only virtual climate surface. Shows effective temperature, observed physical HVAC mode/action, and observed target when unambiguous. |
| `sensor.effective_temperature` | Enabled | None | Calculated zone temperature from included sources. |
| `sensor.effective_humidity` | Enabled when configured | None | Calculated relative humidity. |
| `sensor.temperature_spread` | Enabled with 2+ sources | Diagnostic | Highest minus lowest included temperature. |
| `sensor.valid_temperature_sources` | Enabled | Diagnostic | Count of included temperature sources. |
| `sensor.operating_mode` | Enabled | None | `disabled` or `observe_only`; attributes include the reason code. |
| `sensor.latest_activity` | Enabled | Diagnostic | Short explanation for the newest material zone activity. |
| `binary_sensor.sensor_data_degraded` | Enabled | Diagnostic | On when required source quality/count is insufficient. |
| `binary_sensor.thermostat_data_degraded` | Enabled | Diagnostic | On when any required thermostat is unavailable or contradictory. |
| `binary_sensor.reconciling` | Enabled | Diagnostic | On during startup/reload reconciliation. |
| `switch.observation_enabled` | Enabled | Config | Master Phase 1 enable. Off moves the zone to Disabled; it never controls equipment. |
| `event.activity` | Enabled | Diagnostic | Fires material activity types for Logbook/history visibility. |

### 11.2 Equipment-group entities

| Platform / key | Default | Category | State and purpose |
|---|---:|---|---|
| `sensor.equipment_relationship` | Disabled | Diagnostic | Single, independent, or shared/zoned. |
| `sensor.thermostat_capability_status` | Disabled | Diagnostic | Complete, partial, or unavailable; details are in diagnostics, not large attributes. |
| `binary_sensor.configuration_degraded` | Enabled | Diagnostic | On when a configured entity is missing, duplicated, or incompatible. |
| `event.activity` | Enabled | Diagnostic | Entry-level setup, reload, migration, and Repairs activity. |

### 11.3 Virtual climate behavior

The Phase 1 virtual climate entity intentionally sets `supported_features = 0`. It exposes:

- `current_temperature`: effective zone temperature.
- `current_humidity`: effective zone humidity when configured.
- `hvac_mode`: the common observed thermostat mode, or `None`/unavailable when thermostats disagree.
- `hvac_action`: the common observed action, or the highest-severity observable action when explicitly defined.
- `target_temperature` or range: only when all bound thermostats report an equivalent target within 0.1°C.
- `available`: true after reconciliation when at least one required thermostat and the minimum temperature sources are valid.

The entity does not expose target-temperature, fan-mode, preset-mode, auxiliary-heat, or target-range feature flags. If Home Assistant invokes a setter despite the absent feature flag, the entity raises a translated `HomeAssistantError` stating that Phase 1 is observation-only, records `unsupported_control_attempt`, and sends no service call.

Predictive, model, schedule, manual-override, window-suspension, fan-control, auxiliary-avoidance, and simulation entities are not created in Phase 1. Entity placeholders with unknown states are expressly forbidden.

## 12. Persistence and storage format

### 12.1 Storage ownership

| Data | Owner | Versioning |
|---|---|---|
| Required equipment-group configuration | Parent config-entry data | Config-entry major/minor version |
| Required zone/source configuration | Zone config-subentry data | Parent entry version plus zone `data_version` |
| User observation preferences | Home Assistant config entry options | Config-entry major/minor version |
| Entity/device identity | HA entity and device registries | Home Assistant |
| Runtime reconciliation and history | `Store` key `intelligent_climate.<entry_id>` | Store schema version |
| Normal state history | Home Assistant Recorder/Logbook | Home Assistant |

### 12.2 Runtime Store version 1

```json
{
  "schema_version": 1,
  "entry_id": "01JEXAMPLEENTRY",
  "equipment_group_id": "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3",
  "saved_at": "2026-07-20T15:30:00+00:00",
  "last_clean_shutdown": true,
  "zones": {
    "99246285-6f02-4e8a-94ed-bdfd4a5e62c4": {
      "last_runtime_state": "observing",
      "last_live_observation_at": "2026-07-20T15:29:48+00:00",
      "last_effective_temperature_c": 23.7,
      "last_effective_humidity_pct": 50.0,
      "last_decision_id": "37eaa5de-8a48-47ea-9988-bb0fc2e10a24"
    }
  },
  "source_baselines": {
    "f15f73b1-ea59-4b28-819f-7b99acf065bf": {
      "last_accepted_value": 23.7,
      "last_accepted_at": "2026-07-20T15:29:48+00:00"
    }
  },
  "decisions": [],
  "command_journal": []
}
```

`command_journal` exists for schema continuity but must remain empty in Phase 1. `decisions` is capped at the lower of the configured count and 500 records and pruned at 30 days by default. Only material changes are persisted; repetitive unchanged observations are not history records.

### 12.3 Write policy

- In-memory snapshot updates occur immediately.
- Normal Store writes are debounced for 30 seconds.
- A maximum dirty interval of five minutes guarantees eventual persistence during steady activity.
- Disable/enable changes, migration completion, and clean unload request an immediate save.
- Only one save task may be active per entry.
- Failed writes retain the dirty flag, use bounded retry backoff, log one warning per cooldown, and create a Repairs issue after three consecutive failures.
- A final unload save is awaited for at most five seconds. Failure does not block unload or cause a thermostat command.

### 12.4 Corrupt or missing Store

Because runtime Store data is nonauthoritative, a missing file starts with an
empty runtime. Task 15 quarantines semantically invalid data, preserves future
or unreadable envelopes read-only, and starts live Reconciliation. Only strict
configured-source baselines restore as comparison state; no persisted
temperature or other saved zone observation becomes coordinator/public entity
state.

## 13. Control state machine

Control mode and runtime state are separate values.

`ControlMode` in Phase 1:

- `DISABLED`
- `OBSERVE_ONLY`

`ControlState` in Phase 1:

- `UNLOADED`
- `INITIALIZING`
- `RECONCILING`
- `DISABLED`
- `OBSERVING`
- `DEGRADED`
- `UNLOADING`

### 13.1 Transition table

| From | Trigger / guard | To | Required action |
|---|---|---|---|
| Unloaded | Entry setup begins | Initializing | Parse config, load Store, build dependencies. |
| Initializing | Construction succeeds | Reconciling | Subscribe, inspect sources, start 60-second guard. |
| Initializing | Config/migration failure | Unloaded | Create Repairs issue; fail setup; install no platforms/listeners. |
| Reconciling | Observation disabled | Disabled | Publish disabled snapshot; no command. |
| Reconciling | All required live data valid | Observing | Record reconciliation completion; no command. |
| Reconciling | Guard expires with invalid required data | Degraded | Publish excluded-source reasons and Repairs issue when actionable. |
| Disabled | User enables and live data valid | Observing | Reevaluate immediately; no command. |
| Disabled | User enables but data invalid | Degraded | Explain why observation is degraded. |
| Observing | Required data becomes insufficient | Degraded | Retain last value only in diagnostics; published effective value becomes unavailable. |
| Degraded | Valid data passes two evaluations at least 30 seconds apart | Observing | Clear transient issue/activity state. |
| Observing or Degraded | User disables | Disabled | Stop nonessential reevaluations; keep registry listeners needed for recovery. |
| Any loaded state | Reload starts | Unloading | Remove listeners and flush Store; reload restarts at Initializing. |
| Any loaded state | Entry unload starts | Unloading | Cancel timers/listeners and flush Store. |
| Unloading | Platforms unloaded | Unloaded | Remove runtime. |

### 13.2 Invariants

- Every transition emits at most one material `DecisionRecord`.
- `OBSERVING` requires the minimum valid temperature sources and at least one available bound thermostat.
- `DEGRADED` never substitutes a stale persisted temperature into the public entity state.
- No transition contains a physical command action.
- Startup never transitions directly from Initializing to Observing.
- Recovery from Degraded requires two qualifying evaluations separated by at least 30 seconds, preventing flapping.
- Unknown state/trigger pairs fail closed to Degraded and create an error log; they do not raise out of the coordinator event callback.

### 13.3 Future state reservation

Scheduled control, manual override, away, sleep, vacation, emergency protection, shadow prediction, simulation, and predictive control are not enum values in the Phase 1 runtime. They are documented future migrations, which prevents accidental activation through an option or restored string.

## 14. Failure and fallback matrix

| Failure | Detection | Phase 1 response | User visibility | Recovery |
|---|---|---|---|---|
| Required temperature source unavailable/unknown | HA state | Exclude source; Degraded if minimum count fails | Degraded binary sensor, activity, diagnostics | Two valid evaluations 30 seconds apart |
| Stale source | Age exceeds configured limit | Exclude; no persisted-value fallback | Same, with `stale` reason | Fresh live update plus recovery confirmation |
| Reboot/restored value | Restored-state marker or no live confirmation | Exclude during reconciliation | Reconciling/degraded entity and activity | First plausible live update; jump rules still apply |
| Implausible temperature | Outside configured bounds | Exclude | Diagnostic reason; warning log on transition | Plausible confirmed reading |
| Sudden large jump | Rate threshold exceeded | Hold source out; request confirmation | Diagnostic reason, no repeated warnings | Second reading after 30 seconds confirms range |
| Cross-source outlier | MAD/deviation rule | Exclude only offending source | Source count/spread and diagnostics | Reading returns within threshold |
| Two sensors strongly disagree | Pair spread threshold | Use explicit priority source or publish unavailable | Degraded and contradiction activity | Agreement restored/priority configured |
| Insufficient humidity sources | Minimum count fails | Humidity unavailable; temperature observation may continue | Degraded only if humidity is marked required | Valid humidity data |
| Thermostat unavailable | State unavailable/missing | Climate unavailable; zone Degraded; never change equipment | Binary sensor, activity; Repairs if persistent | Thermostat returns for two evaluations |
| Thermostats report conflicting modes/targets | Normalized values disagree | Do not synthesize a target/mode; mark degraded | Thermostat-data degraded and explanation | States converge or configuration changes |
| Missing stage/aux data | Capability not exposed | Report `not_observable`; make no claim | Diagnostics/capability report | Add a supported external sensor in later phase |
| Entity renamed | Entity registry event | Rewrite validated entity reference and reload | One activity entry | Automatic |
| Entity removed | Registry event/missing state | Degraded and Repairs issue | Repairs plus entity state | Select replacement or remove binding in UI |
| Duplicate thermostat ownership | Config/reconfigure validation | Reject proposed entry/change | Translated flow error | Choose another thermostat/remove prior ownership |
| Unsupported source unit | Unit converter rejects | Exclude source | Degraded plus diagnostic reason | Correct source unit/entity selection |
| Config-entry validation failure | Typed decoder | Abort setup before listeners/platforms | Repairs issue | Reconfigure or successful migration |
| Runtime Store missing | File absent | Start empty and reconcile | Informational debug activity only | Automatic |
| Runtime Store corrupt/future version | Decode/version check | Ignore unsafe runtime data; reconcile | Repairs issue and warning | Delete/reset runtime data through UI repair action or upgrade |
| Runtime Store write failure | Save exception | Keep memory state, bounded retry; no equipment effect | Warning then Repairs after three failures | Successful save clears issue |
| Recorder/Logbook unavailable | Event/recorder failure isolated | Continue coordinator and bounded Store history | Warning log | HA subsystem recovery |
| Registry/listener callback exception | Exception boundary | Log once, mark affected zone Degraded, schedule reevaluation | Degraded/activity | Successful reevaluation |
| Capability changes at runtime | State/registry feature change | Recompute capabilities; update climate presentation | Activity when material | Automatic |
| Setup during HA restart | Startup event/reconciliation | Require live-state confirmation; no burst | Reconciling sensor | Completion or Degraded at timeout |
| Integration unload/crash | HA unload/process loss | Physical thermostat remains in its last independently usable state | Original climate entity remains usable | Reload integration |
| User tries to set virtual climate | Setter called despite no feature | Raise translated error; record attempt; no service call | UI error and activity | Use original thermostat; Phase 2 later |
| Any unexpected command request | Nonempty intent reaches sink | Suppress, error log, Repairs issue, test invariant | Repairs and activity | Correct defect; never execute |

## 15. Logging, reporting, diagnostics, and activity

### 15.1 Python logging

- `DEBUG`: source identifiers, normalized values, exclusion decisions, coalesced triggers, and persistence timing.
- `INFO`: setup/unload, state transitions, meaningful health recovery, configuration changes, and migration completion.
- `WARNING`: sustained unavailable sources, contradictory thermostats, failed Store writes, and unsupported runtime conditions.
- `ERROR`: invariant violations, invalid migrated state, or an attempted nonempty command intent.

Logs use stable reason codes and do not log location names, external account identifiers, or raw diagnostic payloads at normal levels. Repeated warnings are suppressed by a per-reason cooldown.

### 15.2 Activity history

A material activity record is created only for:

- Runtime-state transitions.
- Source inclusion/exclusion transitions.
- Capability changes.
- External physical thermostat mode/target changes observed in Phase 1.
- Configuration, reconfigure, migration, reload, and unload events.
- Repairs issue creation/resolution.
- Unsupported virtual-control attempts.
- Store failures/recovery.

Every record includes timestamp, group/zone IDs, reason code, severity, concise explanation, and a redacted detail object. Unchanged periodic evaluations do not create records.

Phase 1 provides an in-interface activity log through the zone and equipment Event entities, which are visible in Home Assistant Logbook, plus `sensor.latest_activity`. The bounded internal history is included in downloaded diagnostics. A dedicated custom activity panel is deferred with the frontend work.

### 15.3 Home Assistant events

Material activity also fires `intelligent_climate_activity` with:

```text
entry_id, equipment_group_id, zone_id?, activity_type,
reason_code, severity, timestamp, explanation
```

No raw entity state object or sensitive diagnostic field is placed on the event bus.

### 15.4 Diagnostics redaction

Task 12 implements config-entry diagnostics only through
`async_get_config_entry_diagnostics`. Device-specific diagnostics remain
unimplemented. Home Assistant places the returned integration-owned payload
under the downloaded report's `data` section. That payload has
`diagnostics_schema_version: 1` and three stable top-level sections. Schema
version 1 permits backward-compatible additive fields; Tasks 13 and 14 do not
change or remove an existing field:

- `integration`: domain, integration version, and config-entry major/minor
  versions.
- `configuration`: bounded decode status, decoded runtime-configuration state,
  pseudonymized entry/group/zone names, equipment metadata, generated group and
  zone UUIDs, pseudonymized thermostat/source/auxiliary entity references,
  source binding/calibration/weight/priority/enabled metadata, and the
  observation options currently consumed by the coordinator.
- `runtime`: runtime availability, snapshot revision/control state/
  reconciliation/timestamp, thermostat availability and approved capability/
  observed-state fields, per-zone effective values plus deterministic
  configured-order source summaries, bounded activity, and Store health. Task
  13 adds
  `repairs.active_issue_codes`, containing only sorted stable issue-code
  strings. Task 14 adds `activity` and `store` projections; Task 15 adds bounded
  Store migration/recovery health without changing diagnostics schema version
  1.

Per-zone temperature and optional humidity summaries contain configured,
enabled, valid, contributing, and excluded counts; counts for every
`SourceQuality` and `ExclusionReason`; aggregation status/reason codes; and
bounded per-source rows. Source rows contain generated source UUID,
pseudonymized entity reference, binding kind, enabled/contributing/fallback
state, quality/reason, safe timestamps, and restored state. Raw source values
are not diagnostic fields.

The implementation builds this report from decoded immutable configuration
models and the current immutable coordinator snapshot. It never recursively
copies `ConfigEntry.data`, `ConfigEntry.options`, config-subentry data, Home
Assistant `State` objects, complete attribute mappings, or provider-specific
objects. Home Assistant's `async_redact_data` helper is applied only as defense
in depth after the explicit allowlist projection is complete.

Every diagnostic call creates a new 32-byte standard-library random salt. A
small report-scoped pseudonymizer uses HMAC-SHA256 over
`reference_type + NUL + raw_value`, caches results for consistent references
within that report, and emits a bounded 12-hex-character value such as
`entity_ab12cd34ef56` or `name_9812abcdef01`. The secret salt is never returned.
The same typed reference is consistent within one report, while entity/name
pseudonyms ordinarily change between reports. Python `hash()` is not a
serialization or privacy boundary.

The Intelligent Climate data section omits the raw config-entry ID and unique
ID, raw entity IDs, raw user-assigned names, Home Assistant `State` objects and
arbitrary attributes, credentials, coordinates, URLs, and filesystem paths.
Device/entity registry IDs, area IDs, context/user/account identifiers,
authorization data, locations, addresses, webhook IDs, private keys,
environment values, and tracebacks are likewise neither allowlisted nor
copied. Temperatures, humidity, standardized HVAC modes/actions, capability
flags, timestamps, reason codes, and integration-generated equipment-group,
zone, and source UUIDs may remain because they are needed for troubleshooting.
Those generated UUIDs are stable configuration identities and can correlate
multiple reports from the same configuration even though report-scoped entity
and name pseudonyms change.

Home Assistant owns the outer diagnostic envelope and downloaded filename.
Intelligent Climate cannot redact or control those wrapper fields. Depending
on the Home Assistant release, the envelope or filename may include the raw
config-entry ID, Home Assistant version, platform/system information, time
zone, installed custom-integration names and versions, integration
documentation URLs, and other general Home Assistant diagnostic metadata.
Users must review the filename and entire downloaded document, including the
outer envelope, before sharing it publicly.

Loaded entries use their already decoded typed runtime configuration and
current snapshot without mutation. Valid unloaded entries are decoded through
the normal strict persisted-configuration boundary and return
`runtime.available: false`. Awaiting-first-zone and transitional empty-skeleton
entries therefore remain diagnosable. Invalid persisted configuration returns a
bounded `schema_validation`, `entity_validation`, or
`invalid_configuration` category without the exception string, submitted
values, or traceback. Disabled observation returns its real disabled snapshot
without inventing source quality.

Diagnostics perform no network or filesystem I/O, polling, service call, task,
timer, subscription, reload, config mutation, snapshot change, baseline change,
pending-jump change, or coordinator revision change. Tests serialize the final
payload and recursively scan mapping keys and values against realistic
sensitive fixtures. They also verify report-local consistency, cross-report
variation, pseudonym format, generated UUID retention, deterministic source
ordering, quality/reason counts, failed/unloaded/transitional behavior, and
coordinator object/revision identity.

Task 13 reads active Repairs codes from the issue registry without creating,
deleting, or mutating an issue and includes them even when runtime data is
absent or configuration decoding fails. Issue IDs, raw config-entry IDs,
entity IDs, names, translation placeholders, issue data, and issue-registry
objects are never diagnostic fields. Task 14 activity diagnostics use an
explicit typed allowlist containing bounded record identity, generated
group/zone UUIDs, activity type/reason/severity, timestamp, explanation, and
strict scalar detail. Store diagnostics contain only envelope version, bounded
load/recovery status, read-only/quarantine/prior-shutdown flags, restored
baseline count, loaded/dirty state, configured bounds, consecutive failure
count, and last successful-save time. They never contain a quarantine payload.
Diagnostic generation does not load or save Store data, prune mutable history,
schedule a task, register a callback, or fire an event.

### 15.5 Repairs integration

Task 13 centralizes all issue-registry access in `repairs.py`. `IssueCode` is a
stable typed vocabulary with `missing_entity`, `incompatible_entity`,
`migration_failed`, `store_write_failed`, and
`command_boundary_violation`. One entry-scoped manager owns creation,
deletion, entity-condition synchronization, the future Store notification
hook, and the immutable sorted active-code view.

Issue IDs use:

```text
entry_<first 12 lowercase hex characters of
SHA-256("intelligent_climate" + NUL + raw entry ID)>_<issue_code>
```

The raw config-entry ID, unique ID, title, group/zone name, entity ID, and
generated group/zone UUID are absent from the issue ID. Python `hash()` is not
used. Creation of an unchanged existing issue is a no-op, and deleting an
absent issue is harmless.

Every Task 13 issue uses `IssueSeverity.ERROR` because each condition represents
a current observation, persistence, migration, or safety failure.

| Issue code | `is_fixable` | `is_persistent` | Rationale |
|---|---:|---:|---|
| `missing_entity` | False | False | Fully rechecked after startup reconciliation and on existing coordinator evaluations. |
| `incompatible_entity` | False | False | Fully rechecked from current existing source bindings. |
| `migration_failed` | False | True | Must remain visible when migration/validation prevents runtime establishment. |
| `store_write_failed` | False | True | Event notification may otherwise disappear across restart before a successful write. |
| `command_boundary_violation` | False | True | Safety event remains visible until a later clean setup. |

| Issue code | Creation | Clearing |
|---|---|---|
| `missing_entity` | After reconciliation/guard completion, at least one configured thermostat or enabled temperature/humidity source has no Home Assistant State. One issue aggregates the entry. Existing unknown/unavailable States are not missing. Disabled observation does not evaluate sources. | The same evaluation finds no missing required reference. |
| `incompatible_entity` | After reconciliation, an existing nontransient source has a definitive domain/binding/device-class conflict. Missing optional climate attributes, unknown/unavailable, stale, restored, implausible, jump-rejected, outlier, and contradictory observations are not incompatibilities. | Every evaluated existing binding is compatible after state or configuration correction. |
| `migration_failed` | A known config/schema migration or fail-closed persisted/runtime validation boundary fails before setup can complete. Only a bounded failure category is stored; no exception text or malformed document is copied. | A later setup successfully validates the persisted hierarchy. Invalid configuration never loads merely to clear the issue. |
| `store_write_failed` | The Task 14 Store owner reports three or more consecutive write failures through the typed hook. One or two failures do not create it; later failures are idempotent. | The Store owner reports a successful/reset count of zero. |
| `command_boundary_violation` | Any nonempty intent reaches `ObserveOnlyCommandSink`. The intent remains suppressed, the result remains `suppressed_observe_only`, only a stable reason is logged, and no payload is placed in the issue. | A later clean integration setup deletes the stale event issue before observation. Another violation recreates it immediately. |

Missing/incompatible synchronization runs only after the existing startup guard
has completed and then reuses the coordinator's existing targeted state/report
events and watchdog evaluations. It creates no polling, subscription,
independent timer, recurring callback, executor work, filesystem I/O, or
network I/O. The manager compares the current registry entry and updates only
after a material condition/data change. Multiple config entries remain
independent through their hashed entry scopes. Unload cancels coordinator
callbacks but does not delete a still-valid persistent migration, Store, or
command event merely to clean the registry.

Task 14 wires the Store hook to the entry-scoped Runtime Store. Three
consecutive failures create the existing issue and a later successful save
clears it. Only the first failure transition and later recovery are material
activity; exception text is never copied. All English issue titles and
actionable descriptions live under the established `issues` section in
`translations/en.json`. No `RepairsFlow`, fix flow, automatic repair action, or
configuration mutation exists.

When a command-boundary violation occurs, the persistent issue tells the user
that Intelligent Climate blocked the unexpected control attempt, no physical
equipment was commanded, the integration should be disabled, and the defect
should be reported. The sink invokes no physical adapter or Home Assistant
service and preserves the original thermostat for independent control.

### 15.6 Task 14 activity and Store implementation

Task 14 implements `ActivityRecord` as a frozen/slotted value with a UUID
record ID, timezone-aware timestamp, generated equipment-group and optional
zone UUID, stable activity type/reason/severity values, concise explanation,
and a strictly allowlisted scalar detail mapping. It rejects unknown fields,
naive timestamps, incompatible type/reason pairs, nonfinite/nested details,
entity-ID-like explanation text, URLs, and paths.

`ActivityHistory` stores records oldest-to-newest, exposes immutable overall
and per-zone latest views, retains records exactly on the age cutoff, removes
records strictly older than it, and caps count at the lower of the configured
limit and 500. Valid loaded records are sorted/deduplicated deterministically
without listener or event publication; duplicate newly submitted record IDs
are rejected.

Material producers compare semantic state only. Snapshot revision,
`calculated_at`, source report time, capability `discovered_at`, equivalent
watchdog evaluation, and unchanged state reports alone create no activity.
Initial healthy observations establish baselines; initial exclusions may
explain degraded startup. The supported activity surfaces are exactly one
equipment-group Activity Event, one zone Activity Event per configured zone,
and one Latest Activity sensor per zone. Event entity state changes provide
Recorder/Logbook visibility; no second custom Logbook record is emitted.

Every newly accepted record fires exactly one
`intelligent_climate_activity` event containing only entry ID, generated group
and optional zone UUID, activity type, reason, severity, timestamp, and
explanation. Event entity attributes and Latest Activity sensor attributes use
their narrower documented allowlists.

Runtime Store persistence keeps Home Assistant Store version 1, inner
`schema_version: 1`, key `intelligent_climate.<entry_id>`, the existing
`decisions` field, and an always-empty `command_journal`. It uses atomic writes,
a 30-second debounce, five-minute maximum dirty interval, one entry-scoped
writer, bounded retry, and a five-second clean-unload attempt. Current zone
state and source baselines are saved schema-completely but are not restored into
Task 14 live state. Only activity history is restored. Task 15, documented
below, adds migration, corruption quarantine, comparison-only baseline
restoration, and broader restart hardening.

### 15.7 Task 15 migration and recovery implementation

Release 0.0.6 advances the config-entry minor version from 1.0 to 1.1. The
migration decodes and validates the complete parent/options/zone hierarchy in
memory before one `async_update_entry` call. Zone data version 1 is unchanged,
so no subentry mutation is required. Invalid, future, or semantically
inconsistent graphs remain unchanged, create the existing `migration_failed`
Repair, install no runtime listeners or entities, and queue no command.

Home Assistant Store major version 1 and inner `schema_version: 1` remain
unchanged. The Store envelope minor version migrates canonically from 1.1 to
1.2 through the strict runtime decoder and encoder. The existing `decisions`
field remains typed activity history and `command_journal` remains empty.

Runtime loading distinguishes missing, loaded, migrated, quarantined,
unsupported, and failed persistence. A missing Store starts empty.
Semantically invalid data is moved to one bounded entry-scoped quarantine
before the primary key is removed; a later successful clean save replaces it
and clears the migration Repair. Future or unreadable Store envelopes are
preserved read-only to prevent a destructive downgrade. Home Assistant's Store
helper retains syntactically corrupt JSON under its `.corrupt.<timestamp>`
recovery path and creates its standard storage-corruption Repair.

Only configured-source baselines with strict identities and timestamps at or
before the save are admitted. They seed source-health comparison during a new
live reconciliation and are never observations. Persisted zone temperatures,
humidity, runtime state, and timestamps are not loaded into coordinator/public
state. Restored activity is not republished merely because it was loaded.
Unclean prior shutdown creates one bounded lifecycle activity and still
requires live reconciliation.

Diagnostics schema version 1 adds only Store major/minor version, bounded load
status, read-only/quarantine flags, prior-clean-shutdown status, and restored
baseline count. It never includes the quarantine payload. Setup failure,
platform failure, failed platform unload, clean unload, reload, restart,
pending debounce, and multiple-entry cleanup retain one owner for every
listener, callback, timer, and Store task. No path invokes a physical service
or adds a writable capability.

Release 0.0.7 registers one supported Home Assistant shutdown job per loaded
entry. Home Assistant awaits that job before stopping integrations; it performs
the same verified, five-second clean save used by ordinary unload and then
releases the coordinator's entry-scoped subscriptions, timers, callbacks, and
Store tasks. Repeated or concurrent final-save requests are idempotent. An
ordinary unload removes the shutdown job only after platform unload succeeds,
while a failed platform unload preserves the live job and coordinator.

## 16. Testing plan

### 16.1 Tooling and quality gates

- `pytest` with `pytest-homeassistant-custom-component` and deterministic Home Assistant time helpers.
- `pytest-cov` with at least 95% line and 95% branch coverage for `custom_components/intelligent_climate`.
- 100% config-flow step and branch coverage.
- Strict mypy or Home Assistant strict-typing compliance.
- Ruff formatting and linting.
- Home Assistant `hassfest` and HACS validation.
- Python 3.14 CI matching the supplied Home Assistant 2026.7 environment.
- No live network calls and no dependency on a real thermostat.

### 16.2 Unit tests

- Config JSON decoding and semantic validation.
- Temperature conversion in °C and °F.
- Calibration offsets and rounding.
- Unknown, unavailable, nonnumeric, infinite, stale, implausible, restored, and jumping values.
- MAD outlier handling for 1, 2, 3, and many sensors.
- Mean, median, weighted, and priority aggregation.
- Contradictory two-sensor behavior.
- Thermostat capability normalization.
- Missing stage/auxiliary representation as not observable.
- Every legal control-state transition.
- Every illegal transition's fail-closed behavior.
- Activity pruning by count and age.
- Store schema decode, encode, and migration helpers.
- Redaction of every sensitive key class.

### 16.3 Integration tests

- Complete initial config flow, including multiple zones and shared equipment.
- Options changes and reload.
- Parent and zone-subentry reconfiguration of thermostat membership.
- Duplicate thermostat rejection across entries.
- Config-entry/subentry setup, unload, reload, removal, and migration.
- Device and entity registry creation and stable unique IDs.
- Entity rename and removal handling.
- Observe-only climate values for single and conflicting thermostats.
- Sensor changes coalesced into one evaluation.
- Stale-source watchdog deadline.
- Restart with clean Store, missing Store, corrupt Store, and restored source states.
- Repairs issue creation, persistence, and clearing.
- Redacted diagnostics snapshot.
- Event entity and event-bus activity payload.
- Store write failure/retry behavior.
- Home Assistant stop during a pending debounce.

### 16.4 Mandatory no-command tests

These tests are release blockers:

1. Patch `hass.services.async_call` and fail the test if a call targets `climate`, `fan`, `humidifier`, `water_heater`, `switch`, `input_number`, or any configured physical entity's domain.
2. Exercise every config option, state transition, source failure, restart path, virtual climate setter, reload, and unload.
3. Assert the command journal remains empty.
4. Assert every decision has `command_status` equal to `NONE` or `SUPPRESSED_OBSERVE_ONLY`.
5. Mutation-test the command sink boundary so a nonempty intent is always suppressed and raises an internal invariant report.

### 16.5 Deterministic supplied Nest fixture

The supplied redacted Nest diagnostic becomes a sanitized fixture with:

- HA Core 2026.7.2 and Python 3.14.6.
- Online thermostat.
- Available modes Heat, Cool, Heat/Cool, and Off.
- Observed mode Cool and HVAC action Off.
- Current temperature about 23.69°C.
- Current humidity 50%.
- Cooling setpoint 25.0°C.
- Fan timer capability present.
- No claim of HVAC stage or auxiliary heat observability.

Tests confirm the virtual climate reports these observations accurately and does not infer unsupported features.

### 16.6 CI release gate

A Phase 1 release candidate is rejected if any of the following occurs:

- Coverage is below threshold.
- A config-flow branch lacks a test.
- Hassfest, HACS, typing, linting, or tests fail.
- A platform performs blocking I/O on the event loop.
- A diagnostic snapshot contains a raw entity ID or user-assigned name.
- A test observes any physical-control service call.
- Runtime history exceeds its configured bound.

## 17. Exact Phase 1 acceptance criteria

Every criterion below is mandatory. “Pass” means the stated evidence exists in automated tests or documented manual validation; partial completion does not pass.

| ID | Acceptance criterion | Required evidence |
|---|---|---|
| P1-AC-001 | The repository matches the Phase 1 structure, contains a valid HACS manifest, and passes HACS and hassfest validation. | CI artifacts. |
| P1-AC-002 | The integration declares Home Assistant 2026.7.0 as its minimum and installs/loads on the supplied HAOS/Core 2026.7.2 profile. | Manifest plus setup test/manual smoke test. |
| P1-AC-003 | A user can create an equipment group and its first zone entirely through one UI flow, then add/reconfigure/remove additional zone subentries through the integration UI without YAML or manual file editing. | Full parent/subentry-flow tests and UI walkthrough. |
| P1-AC-004 | A config entry can contain one or more thermostats and one or more zones, including an explicitly modeled shared/zoned relationship. | Multi-zone/shared fixture test. |
| P1-AC-005 | A thermostat cannot be owned by two Intelligent Climate config entries. | Duplicate-flow and reconfigure tests. |
| P1-AC-006 | Options flow can enable/disable observation and change aggregation, freshness, outlier, and bounded-history settings; zone reconfigure can change source calibration/weights/priority. | Every options and subentry-reconfigure branch tested. |
| P1-AC-007 | Parent reconfigure can change equipment name/type, thermostat membership, and relationship; zone reconfigure can change zone membership/sources without changing stable group/zone unique IDs. | Registry identity assertions before/after both flows. |
| P1-AC-008 | Config-entry unload and reload remove/recreate all listeners, timers, runtime objects, platforms, and services without leaks. | Listener/timer/runtime assertions. |
| P1-AC-009 | Config-entry and Store version migrations are transactional; an unresolvable migration fails setup safely and creates a Repairs issue. | Success and failure migration tests. |
| P1-AC-010 | Each equipment group and zone has a stable device-registry identifier; every entity unique ID is derived from an immutable group/zone UUID, not its name or current entity ID. | Registry tests. |
| P1-AC-011 | Runtime capability discovery accurately represents modes/features and labels missing stage/auxiliary data `not_observable`. | Generic and Nest capability fixtures. |
| P1-AC-012 | Every zone creates the exact applicable Phase 1 entity set in Section 11 and creates no predictive, model, schedule, override, fan-control, or simulation placeholders. | Entity inventory snapshot. |
| P1-AC-013 | The virtual climate entity reports effective current conditions and only unambiguous observed mode/action/target values. | Single and conflicting thermostat tests. |
| P1-AC-014 | The virtual climate advertises no writable climate feature, and every setter path returns a translated observation-only error. | Entity feature/setter tests. |
| P1-AC-015 | Across all automated Phase 1 scenarios, zero service calls capable of changing physical climate equipment occur and the command journal remains empty. | Mandatory no-command suite. |
| P1-AC-016 | Temperature inputs in supported units are normalized to Celsius, calibrated, aggregated, and presented in the user's Home Assistant unit system. | °C/°F conversion tests. |
| P1-AC-017 | Mean, median, weighted-average, and priority temperature aggregation produce deterministic documented results. | Parameterized unit tests. |
| P1-AC-018 | Unknown, unavailable, nonnumeric, nonfinite, unsupported-unit, implausible, stale, restored, jumping, outlier, and contradictory inputs are excluded with an exact reason code. | Parameterized health tests. |
| P1-AC-019 | A reboot/restored value and an unconfirmed jump cannot become the public effective temperature. | Restart/jump integration tests. |
| P1-AC-020 | Falling below the minimum valid temperature-source count makes the effective temperature unavailable and the zone Degraded; it never reuses a stale persisted value publicly. | Source-loss and restart tests. |
| P1-AC-021 | Degraded-to-Observing recovery requires two valid evaluations at least 30 seconds apart. | Deterministic-clock state test. |
| P1-AC-022 | Startup and reload always enter Reconciliation and never issue or queue a control command. | Restart/reload state and no-command tests. |
| P1-AC-023 | An unavailable or conflicting thermostat degrades the zone without changing the original thermostat, which remains usable independently. | Unavailable/conflict/unload tests. |
| P1-AC-024 | The runtime Store follows schema version 1, batches writes, bounds activity to 500 records and 30 days by default, and never writes per source update. | Storage serialization/timing/pruning tests. |
| P1-AC-025 | A missing or corrupt runtime Store cannot block safe observation startup; corrupt/unsupported data produces a Repairs issue and is not trusted. | Store failure tests. |
| P1-AC-026 | Material activities appear through Event entities/Home Assistant Logbook, update Latest Activity, and remain available in bounded redacted diagnostics. | Event/entity/diagnostic tests plus UI walkthrough. |
| P1-AC-027 | Normal logging includes setup, transitions, failures, and recovery with stable reason codes and warning cooldowns. | Log-capture assertions. |
| P1-AC-028 | Diagnostics redact raw entity IDs, names, device/area/context/user/account identifiers, URLs, coordinates, and tokens. | Redaction snapshot and forbidden-string scan. |
| P1-AC-029 | Actionable missing/incompatible entities, migration failures, repeated Store failures, and command-boundary violations create Repairs issues; recovery clears resolvable issues. | Repairs lifecycle tests. |
| P1-AC-030 | The coordinator is event driven, coalesces bursts within 250 ms, evaluates only affected zones, and performs no blocking event-loop I/O. | Coordinator timing/instrumentation tests. |
| P1-AC-031 | Test coverage is at least 95% line and branch for the integration and 100% for config-flow branches. | CI coverage report. |
| P1-AC-032 | All tests use deterministic clocks/data and require no cloud account, network call, or real HVAC equipment. | CI network isolation and fixture review. |
| P1-AC-033 | Predictive control, adaptive start/stop, thermal modeling, confidence scores, and forecast-based decisions are absent from the Phase 1 runtime and cannot be enabled by config, option, service, restored state, or entity. | Forbidden-option/entity tests and package review. |
| P1-AC-034 | User-facing documentation explains Phase 1 observation-only behavior, entity meanings, source exclusions, diagnostics, Repairs, and how to continue using the original thermostat. | Documentation review checklist. |
| P1-AC-035 | The supplied Nest fixture reports Cool mode, Off action, approximately 23.69°C, 50% humidity, and 25.0°C cool target without asserting stage or auxiliary-heat status. | Fixture-specific integration test. |

Phase 1 is accepted only when P1-AC-001 through P1-AC-035 all pass.

## 18. Phase 2 handoff contracts

Phase 1 leaves deliberate extension points without implementing control:

- `CommandSink`: Phase 2 may add an active implementation only behind explicit Scheduled Control enablement and safety gates.
- `DecisionRecord`: Phase 2 may add a real proposed command and correlation metadata while preserving reason codes.
- `command_journal`: Phase 2 may begin persisting bounded correlation records.
- `ControlMode` and `ControlState`: Phase 2 adds scheduled, override, occupancy, suspension, and emergency states through a config/store migration.
- Zone input bindings already carry optional window, occupancy, stage, and fan entity references.
- Shared-equipment metadata exists, but active arbitration remains prohibited until its Phase 5 behavior and tests are complete.
- The frontend remains a separate package and consumes supported entity/event/WebSocket APIs rather than private Home Assistant internals.

## 19. Known limitations and assumptions

- Home Assistant integrations differ in how frequently they update unchanged sensor states. The 30-minute default freshness limit is configurable and may need adjustment for a cloud thermostat.
- Home Assistant cannot always identify whether a future thermostat change originated at the wall device or another automation. Phase 1 records all such changes as external observations and makes no manual-override claim.
- Several thermostats may expose different modes or target semantics. Phase 1 publishes a shared virtual value only when it is unambiguous.
- The Nest diagnostic demonstrates temperature, humidity, target, HVAC mode/action, and fan-timer traits, but does not prove stage or auxiliary-heat observability.
- Event entities and Logbook satisfy the Phase 1 in-interface activity requirement. A dedicated browsable activity panel belongs with later frontend delivery.
- Equipment type and shared policy are descriptive in Phase 1. No equipment-specific control or safety inference occurs.
- Observation-only mode cannot enforce freeze, heat, humidity, window, fan, or auxiliary-heat policies. Those protections remain the responsibility of the physical thermostat and existing Home Assistant automations until active scheduled control is delivered and accepted.
- Loss of Home Assistant or this integration leaves the physical thermostat untouched and usable through its original entity or physical interface.

## 20. Implementation start gate

Implementation may begin when this design is approved. The first code increment should contain only package scaffolding, typed configuration models, config flow, and validation tests. The command sink invariant and its failing sentinel test should be added before the coordinator or virtual climate entity so later Phase 1 work cannot accidentally acquire a physical-control path.

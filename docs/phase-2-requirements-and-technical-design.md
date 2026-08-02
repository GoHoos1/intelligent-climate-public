# Intelligent Climate

## Phase 2 Requirements Review and Technical Design

**Phase:** 2 — Safe Scheduled Control  
**Baseline release:** 0.0.8 (Phase 1 accepted)  
**Design status:** Approved implementation baseline; Task 1 commenced with no runtime behavior  
**Prepared:** July 29, 2026  
**Target platform:** Home Assistant 2026.7 API family; minimum supported Core 2026.7.0  
**Primary deployment profile:** Home Assistant OS 18.1, Core 2026.7.2, Python 3.14.6, aarch64, `America/New_York`

---

# Contents

- [Executive outcome](#executive-outcome)
- [1. Governing baseline](#1-governing-baseline)
- [2. Requirements traceability review](#2-requirements-traceability-review)
- [3. Phase transition and safety invariant](#3-phase-transition-and-safety-invariant)
- [4. Architecture and repository changes](#4-architecture-and-repository-changes)
- [5. Weekly schedule model, validation, precedence, and persistence](#5-weekly-schedule-model-validation-precedence-and-persistence)
- [6. Time-zone, DST, midnight, and week-boundary behavior](#6-time-zone-dst-midnight-and-week-boundary-behavior)
- [7. Manual-override design](#7-manual-override-design)
- [8. Schedule UI and backend/frontend boundary](#8-schedule-ui-and-backendfrontend-boundary)
- [9. Control and arbitration state machine](#9-control-and-arbitration-state-machine)
- [10. Absolute limits, intervals, deadbands, and cooldowns](#10-absolute-limits-intervals-deadbands-and-cooldowns)
- [11. Command adapter, correlation, acknowledgement, retry, and failure](#11-command-adapter-correlation-acknowledgement-retry-and-failure)
- [12. Window and door handling](#12-window-and-door-handling)
- [13. Occupancy modes](#13-occupancy-modes)
- [14. Entities, actions, events, activity, diagnostics, and Repairs](#14-entities-actions-events-activity-diagnostics-and-repairs)
- [15. Storage migration and startup/reload reconciliation](#15-storage-migration-and-startupreload-reconciliation)
- [16. Shared-equipment conflict resolution](#16-shared-equipment-conflict-resolution)
- [17. Basic fan control and humidity/dew-point lockouts](#17-basic-fan-control-and-humiditydew-point-lockouts)
- [18. Failure and fallback matrix](#18-failure-and-fallback-matrix)
- [19. Testing strategy](#19-testing-strategy)
- [20. Exact Phase 2 acceptance criteria](#20-exact-phase-2-acceptance-criteria)
- [21. Dependency-ordered private-first implementation backlog](#21-dependency-ordered-private-first-implementation-backlog)
- [22. Known limitations and assumptions](#22-known-limitations-and-assumptions)
- [23. Approval gates before implementation](#23-approval-gates-before-implementation)
- [24. Evidence and references](#24-evidence-and-references)

# Executive outcome

Phase 2 replaces the Phase 1 observation-only development invariant with a guarded-command invariant. Observe Only remains permanently supported. Phase 2 also adds Manual Control, in which all autonomous scheduling and intelligent behavior is off but deliberate user-initiated commands remain available through the virtual climate entity, sidebar, and cards. A new Scheduled Shadow mode evaluates the complete schedule, arbitration, override, window, occupancy, fan, and safety path but emits no physical service calls. Physical Scheduled Control cannot be armed until the entry passes a visible shadow-readiness gate and the user explicitly confirms control authority.

The design deliberately keeps the physical thermostat authoritative and independently usable. Intelligent Climate sends sparse, idempotent setpoint or supported fan commands through Home Assistant; it does not directly cycle compressors, bypass native thermostat protections, continuously “correct” the thermostat, or require Home Assistant to remain online for HVAC to function.

Monitoring is independent from automation. Observe Only, Manual Control, Scheduled Shadow, Scheduled Control, Safe Fallback, and Emergency Pause continue to expose sensor, thermostat, equipment-state, weather, activity, and diagnostic information. Observe Only may run indefinitely and emits no physical calls. Phase 2 preserves Recorder-compatible history and bounded activity; the dedicated model-ready observation store and thermal-property analysis remain Phase 3 and will collect while the user stays in Observe Only or Manual Control.

The Phase 2 user experience includes:

- A responsive Intelligent Climate sidebar application with Overview, Schedule, Control, Sensors, Activity, and Settings/Diagnostics routes.
- A practical weekly schedule editor with multiple periods, single or heat/cool targets, tolerance, day copying, weekday/weekend templates, enablement, validation, and preview.
- A Manual Control workflow for target, supported mode, and supported fan changes with automation off, without requiring a schedule or shadow qualification.
- A zone card for status and temporary control on ordinary dashboards.
- A schedule card for current period, next transition, and a deep link to the editor.
- A truthful Today climate timeline and concise status explanation showing the data Phase 2 actually has: indoor/outdoor observations, scheduled and effective targets, equipment action, weather context, and material control events.
- Progressive disclosure: ordinary status and control first; advanced Phase 2 safety, source, window, occupancy, fan, and diagnostic settings remain available without YAML.

The Phase 2/Phase 7 UI boundary is explicit. Phase 2 ships a complete, keyboard-accessible core schedule editor and a useful factual current-day climate timeline. Phase 3 adds shadow-prediction, confidence, and prediction-error overlays; Phase 4 adds forecast-driven planned-action overlays and daily plan/after-action narratives. Phase 7 retains the advanced drag-and-resize schedule timeline, date-specific exceptions, vacation-calendar authoring, schedule import/export, the isolated Simulation Lab, interactive comparison/replay/simulation overlays, advanced equipment/model dashboards, and extensive visual card customization.

Two later-phase contracts are now explicit. The Phase 7 Simulation Lab is a separate execution context with virtual inputs, a virtual clock, and a simulation-only command sink; it can reuse pure decision logic but cannot construct the physical adapter or alter live control. Phase 4 may add opt-in psychrometric comfort targeting to predictive scheduling. That feature must produce a bounded, explainable effective temperature target and fall back to the ordinary schedule whenever required inputs or confidence are insufficient; active humidity-equipment control remains Phase 6.

Visualization and narrative are nonauthoritative presentation layers. Backend contracts identify every series or statement as measured, configured, calculated, forecast, predicted, or planned. A deterministic local formatter may explain only typed decision/model facts and has no path to create or modify a command. It cannot claim that clouds, heat, a schedule, or another factor influenced a decision unless the control record names that influence, and it cannot claim that a model was adjusted unless a validated model update was committed.

Shared equipment receives a Phase 2 safety arbitration layer, not Phase 5 optimization. A shared/zoned group has one explicitly designated command-authority thermostat in Phase 2. Other related thermostats remain observed and participate in override/conflict detection. Zone priority resolves simultaneous compatible demand; opposite-direction demand or an external conflicting thermostat state causes command suppression and a visible conflict hold. Multi-controller optimization, anti-starvation, damper/stage intelligence, and coordinated commands across multiple physical control authorities remain Phase 5.

# 1. Governing baseline

## 1.1 Source precedence

When sources differ, this design applies the following precedence:

1. `nonnegotiable-requirements.txt`
2. `architecture-decisions.txt`
3. The user’s Phase 2 instructions in this review
4. Phase 2 boundaries in `Master-specifications.txt`
5. Remaining requirements in `Master-specifications.txt`
6. Accepted Phase 1 contracts in release 0.0.8
7. The original Phase 1 technical design where it still matches 0.0.8

The accepted implementation, tests, and acceptance record are evidence of the stable Phase 1 baseline. They are not permission to retain a Phase 1-only constraint when Phase 2 explicitly replaces it.

## 1.2 Verified Phase 1 baseline

Release 0.0.8 is the accepted Phase 1 release:

- All 35 Phase 1 acceptance criteria passed.
- 817 automated tests passed.
- Statement coverage was 97.88%; branch coverage was 95.21%.
- The mandatory no-physical-control suite passed all 25 tests.
- Config entry schema is 1.1.
- Zone data version is 1.
- Runtime Store envelope is 1.2 with inner schema version 1.
- The existing runtime Store contains bounded activity in `decisions`, comparison-only source baselines, restart metadata, and an always-empty `command_journal`.
- `OperatingMode` exposes only `disabled` and `observe_only`.
- The virtual zone climate entity advertises `ClimateEntityFeature(0)` and rejects setters.
- `ObserveOnlyCommandSink` is the only command sink and structurally cannot call a physical Home Assistant action.
- The coordinator is typed, event driven, entry scoped, uses `ConfigEntry.runtime_data`, and performs targeted reevaluation.
- The Phase 1 entity inventory includes read-only climate, observation/health sensors, diagnostic activity surfaces, and an observation-enabled switch.
- Configuration, activity, diagnostics, Repairs, Store migration/quarantine, startup reconciliation, and shutdown persistence are already established contracts.

Phase 2 must preserve these behaviors except where an acceptance criterion below explicitly changes them.

## 1.3 Phase 1 contracts that remain unchanged

- One config entry represents one equipment group.
- Zones remain native config subentries and child devices.
- Stable group, zone, and source UUIDs remain immutable.
- A thermostat belongs to at most one Intelligent Climate entry.
- Required structural bindings remain in config-entry/subentry data.
- Runtime objects remain entry scoped in `ConfigEntry.runtime_data`.
- Source values remain normalized to Celsius internally.
- Bad, stale, restored, implausible, jumping, outlier, or contradictory observations remain excluded.
- Persisted temperatures never become live public observations.
- Configuration and persistence migrations remain strict, transactional where possible, and fail closed.
- Diagnostics remain allowlisted and redacted.
- Activity remains material-only, bounded, and visible in Home Assistant.
- No private Home Assistant API, monkey patch, unsupported frontend mutation, or YAML-only configuration is introduced.

# 2. Requirements traceability review

## 2.1 Disposition vocabulary

- **Included:** Required for Phase 2 acceptance.
- **Included, limited:** A safe baseline is delivered now; advanced behavior is reserved for a later named phase.
- **Deferred:** Explicitly excluded from Phase 2 runtime.
- **Clarified:** Included after resolving ambiguous wording.
- **Superseded:** A Phase 1-only constraint is replaced by a stricter Phase 2 contract.

## 2.2 Product decision register

| ID | Product decision | Resolution |
|---|---|---|
| PD-01 | Schedule UI versus Phase 7 advanced editor | Phase 2 delivers a complete form/timeline hybrid weekly editor: period add/edit/delete, multiple periods, target/range, tolerance, labels, copy day, weekday/weekend templates, enable/preview, validation, and responsive accessibility. Phase 7 owns drag/resize authoring, date/vacation exceptions, import/export, predictive overlays, and extensive card styling. |
| PD-02 | Sidebar and dashboard cards | Phase 2 ships one sidebar panel plus a zone card and schedule card. The frontend is independently built and versioned, but release artifacts are bundled with the integration. Cards use a small Phase 2 visual editor for entry/zone/density/control visibility; Phase 7 adds advanced visual customization. |
| PD-03 | Shared-equipment conflict boundary | Phase 2 implements safety arbitration with one command-authority thermostat per shared group, priority-based compatible demand, and fail-closed conflict hold. Coordinated optimization across multiple physical control authorities remains Phase 5. |
| PD-04 | Mandatory dry run | Scheduled Shadow is mandatory before active control. Qualification requires at least 24 continuous hours, 20 evaluated would-command decisions, two material schedule transitions for every enabled zone, at least 95% valid control evaluations, and no unresolved blocking fault. A seven-day shadow period is recommended. |
| PD-05 | Schedule time zone | Weekly schedules use the Home Assistant configured IANA time zone and local wall time. A time-zone change blocks active commands, returns the entry to shadow/reconciliation, and requires administrator acknowledgement. |
| PD-06 | Schedule gaps | The weekly schedule is circular. A period remains active until the next material transition. Before a day’s first period and on an empty day, the engine inherits the most recent period from the prior seven days. At least one enabled weekly period is required. |
| PD-07 | DST behavior | A nonexistent spring-forward transition executes once at the first valid instant after the gap. An ambiguous fall-back transition executes only on the first occurrence. A persisted transition key prevents duplicate execution. |
| PD-08 | External changes outside configured limits | Intelligent Climate never creates an out-of-limit command. A physical or third-party change outside Intelligent Climate limits is treated as an external override, causes Intelligent Climate command suspension, and raises an actionable alert; it is not immediately counter-commanded. |
| PD-09 | Override next-transition meaning | “Next scheduled setpoint transition” means the next strict-future boundary that materially changes the effective scheduled controlled target after occupancy overlays. Same-value labels do not expire the override. |
| PD-10 | Startup mismatch | A thermostat/schedule mismatch discovered during startup is presumed external unless a persisted, bounded command record can prove it was an acknowledged Intelligent Climate result. The default is a manual override through the next material transition, not an immediate catch-up command. |
| PD-11 | Command acknowledgement | Home Assistant action-call success is not acknowledgement. The resulting thermostat state must semantically match the requested state within the acknowledgement window. |
| PD-12 | Retry policy | A scheduled or override idempotent target command may be retried once only when the pre-command state is unchanged, no external context/change is observed, all safety gates still pass, and the minimum interval permits it. Manual Control commands, mode reversals, fan restores, and uncertain partial transactions are not automatically retried. |
| PD-13 | Occupancy effect | Each occupancy mode chooses exactly one Phase 2 effect per zone: select a weekly profile, apply a bounded setpoint offset, or no target effect. Predictive preconditioning is deferred. |
| PD-14 | Emergency protection and pause | Optional temperature protection may override schedule, occupancy, manual override, and window suspension, but never Disabled, Emergency Pause, invalid configuration, thermostat unavailability, command uncertainty, or an unsupported capability. The physical thermostat remains the ultimate fallback. |
| PD-15 | Historical UI scope | Phase 2 shows current observation/control data, a built-in bounded 48-hour Presentation Trace Store for the Today timeline, bounded decision/activity history, command attempts, overrides, transitions, and public entity history where Recorder makes it available. The presentation trace is rounded, nonauthoritative, isolated from authoritative runtime state, and never used for control or learning. Long-horizon model, performance, energy, and simulation history belongs to later phases. |
| PD-16 | Authority and permissions | Any authenticated user may view and request a safe temporary zone override. Administrator permission is required to edit schedules/settings, acknowledge migration/time-zone faults, arm physical control, change control authority, or clear a command lockout. |
| PD-17 | Schedule exceptions | Manual overrides are the Phase 2 temporary exception mechanism. Date-specific exceptions and vacation-calendar schedules remain Phase 7, while the Vacation occupancy mode and a dedicated vacation weekly profile are included now. |
| PD-18 | Direct thermostat cycling | Phase 2 commands supported thermostat setpoints/modes and supported circulation fan controls only. It never directly cycles compressors, stages, dampers, auxiliary heat, humidifiers, dehumidifiers, or ventilation equipment. |
| PD-19 | Simulation architecture and panel | Phase 7 delivers a dedicated Simulation Lab with virtual thermostat, indoor/outdoor conditions, weather, contacts, occupancy, equipment/fan state, faults, and pause/step/accelerate controls. It is an isolated execution context, not a live mode switch: it uses a simulation input provider, virtual clock, separate state/storage namespace, and simulation-only command sink and cannot construct the active adapter or mutate live schedules, overrides, qualification, journals, or equipment. Phase 2 preserves this boundary by keeping policy engines pure and command sinks injected. |
| PD-20 | Psychrometric comfort targeting | Phase 4 may add an opt-in **Use psychrometric comfort** schedule/profile setting. It may convert a temperature-like comfort target into a bounded, explainable effective temperature target and alter predictive start/stop timing using trustworthy psychrometric observations and forecasts. Disabled, stale, invalid, or low-confidence operation uses the ordinary scheduled temperature unchanged. Phase 6 owns active humidity-equipment control. |
| PD-21 | Automation-off manual operation | Phase 2 adds **Manual Control** as a normal operating mode distinct from Disabled, Observe Only, Scheduled Control, and Manual Override. Schedules, occupancy effects, contact responses, predictive/learned behavior, automatic fan circulation, and every other autonomous trigger are inactive. A current explicit user action may create one capability-valid, ownership-valid, absolute-limit-valid command through the normal journal, correlation, acknowledgement, and failure path. Manual Control requires no schedule or shadow qualification and never retries or reasserts a target because a sensor, timer, restart, or external thermostat change occurred. |
| PD-22 | Observation as a permanent data mode | Observe Only is a first-class indefinite zero-command mode, not merely a commissioning step. All useful live status, sensor quality, weather, activity, and diagnostics remain available. Phase 2 retains Recorder-compatible public history and bounded internal activity without claiming learned thermal properties; Phase 3 adds the dedicated model-ready observation store and thermal analysis, which collect independently of whether automation is off, shadowed, or active. |
| PD-23 | Progressive climate visualization | Visualization is not postponed to Phase 7. Phase 2 provides a factual Today timeline with observed indoor/outdoor conditions, scheduled and effective target steps, actual equipment action, and material event annotations. Phase 3 adds predicted indoor trajectories, confidence bands, arrival/error views, and a factual learning retrospective. Phase 4 adds forecast-driven start/stop/coast plans, influence annotations, a daily plan briefing, and measured-versus-planned after-action narrative. Phase 7 adds interactive comparison, replay, simulation overlays, and advanced model/performance exploration. |
| PD-24 | Narrative provenance and authority | Status summaries, daily briefings, and retrospectives are generated locally from typed fact packets. The canonical formatter is deterministic and has no command authority. Missing data is stated, not inferred; weather or solar influence is named only when recorded by the applicable decision/model; and model adjustment is named only after a committed validated update. Optional future language restyling may not add facts, change confidence, or influence control. |

## 2.3 Scope summary

### Included in Phase 2

- Observe Only, Manual Control, Scheduled Shadow, Scheduled Control, Manual Override, occupancy overlays, window suspension, safe fallback, and optional emergency temperature protection.
- Continuous sensor/climate/weather/equipment/activity visibility in every loaded operating mode, including when every automated feature is off.
- Weekly local-time schedules and occupancy-selectable weekly profiles.
- Manual override detection, creation, extension, cancellation, persistence, and all six specified expiration policies.
- Command planning, capability checks, safety validation, correlation, acknowledgement, bounded retry, cooldown, journal, and failure lockout.
- Conservative startup/reload reconciliation and command suppression.
- Window and exterior-door configuration, debounce, grace, resume, reminders, zone/group suspension, and protection bypass.
- Home, Away, Sleep, Vacation, Guest, and custom occupancy modes with delays and transparent source reasoning.
- Basic shared-equipment safety arbitration.
- Basic circulation fan control with spread, schedule, occupancy, runtime, quiet-period, humidity, dew-point, and post-cooling restrictions.
- A professional sidebar application, factual Today timeline/current-status explanation, and two reusable Lovelace cards.
- A bounded 48-hour rounded presentation trace used only for visualization and resilient across ordinary restarts; it is not the Phase 3 model-ready observation store.
- Phase 2 entities, actions, events, activity, diagnostics, Repairs, migration, tests, and documentation.

### Deferred from Phase 2

- Thermal learning, coefficients, confidence models, and model storage: Phase 3.
- Predictive shadow results, predicted indoor trajectory/confidence, predicted arrival/start/time-to-target, model comparison, and factual learning retrospective: Phase 3.
- Adaptive start/stop, forecast-driven commands, planned-action overlays, influence annotations, and daily plan/after-action narratives: Phase 4.
- Auxiliary-heat intelligence, stage-aware control, multi-authority shared-equipment optimization, anti-starvation, damper coordination, and performance alerts: Phase 5.
- Humidifier, dehumidifier, ERV/HRV, ventilation, air-quality, energy-price, demand-response, and advanced circulation: Phase 6.
- The isolated Simulation Lab, virtual input controls, virtual clock, fault injection, replay, date-specific schedule exceptions, vacation-calendar editing, advanced drag schedule editing, schedule import/export, interactive comparison/replay/simulation overlays, advanced model/performance dashboards, and extensive card styling: Phase 7.
- Opt-in psychrometric comfort targeting for adaptive start/stop and bounded effective temperature targets: Phase 4. Active humidifier, dehumidifier, and ventilation coordination remains Phase 6.

## 2.4 Traceability: platform, safety, and control

| Requirement | Source | Disposition | Phase 2 interpretation and design location |
|---|---|---|---|
| P2-R-001 UI-only configuration | Nonnegotiable 1; architecture decision 1; Master §1 | Included | Config/reconfigure flows plus sidebar settings and authenticated WebSocket mutations; no YAML or Store editing. §§4, 8. |
| P2-R-002 Multiple independent or related thermostats | Nonnegotiable 2; Master §§2–3 | Included, limited | Independent thermostats are controlled independently. Shared equipment uses one command authority and safety arbitration. §§12, 16. |
| P2-R-003 Respect discovered thermostat capabilities | Master §3 | Included | Capability intersection and per-command validation precede every plan. Unsupported modes/features never create commands. §11. |
| P2-R-004 Existing thermostat remains usable | Nonnegotiable 12; Master §§3, 14 | Included | No replacement of physical entity; sparse setpoint control; no dependency on continuous HA commands. §§3, 11, 18. |
| P2-R-005 Virtual climate becomes safe control surface | Master §3 | Included | Setters are enabled in Manual Control for explicit user commands and in active Scheduled Control for bounded overrides; Observe/Shadow remain read-only. §§3, 8, 14. |
| P2-R-006 Bad/stale sensors cannot create extreme control | Nonnegotiable 5; Master §§8, 14 | Included | Phase 1 quality pipeline remains; command gate requires trustworthy current temperature and applies absolute limits. §§10, 15. |
| P2-R-007 Safety over optimization | Master §14 | Included | Fixed precedence and post-arbitration safety validation. §§9–10. |
| P2-R-008 Absolute heating/cooling limits | Master §14; user request | Included | User limits intersect thermostat advertised limits and immutable finite-value/range invariants. §10. |
| P2-R-009 Minimum command rates/deadband/cooldowns | Master §11; user request | Included | Per-thermostat automatic interval, mode-reversal cooldown, semantic deadband, failure cooldown, and dedupe. §10. |
| P2-R-010 Freeze/excessive-heat protection | Master §14 | Included, limited | Optional temperature protection only; humidity equipment protection deferred, humidity fan lockout included. §§9–10, 17. |
| P2-R-011 Sensor/thermostat/conflict/command/restart failures | Master §14 | Included | Fail-closed matrix, safe fallback, lockout, Repairs, and no burst on startup. §§15, 18. |
| P2-R-012 Master enable and emergency pause | Master §14 | Included | Turning automation off enters Manual Control or user-selected Observe Only without changing the thermostat; Emergency Pause suppresses all integration commands. §§3, 8–9, 14. |
| P2-R-013 Scheduled control before learning | Nonnegotiable 7; Master §§6, 23 | Included | Deterministic schedule engine has no model or forecast dependency. §§5–7. |
| P2-R-014 Weather loss does not stop ordinary control | Nonnegotiable 10; Master §10 | Included | Weather is display-only in Phase 2 and absent from control decisions; loss marks UI degraded only. §8. |
| P2-R-015 Restart never causes unsafe command | Nonnegotiable 11; Master §14 | Included | Quiet reconciliation, mismatch-as-override, transition ledger, dedupe, and one-plan release. §15. |
| P2-R-016 Observe Only retained | User request; Phase 1 contract | Included | Permanent indefinite zero-command operating mode and selectable fallback with full visibility. Dedicated model-ready storage remains Phase 3. §§3, 8–9, 14, 22. |
| P2-R-017 Shadow clearly shows without executing | Nonnegotiable 17; Master §15; user request | Included | Full command path through `ShadowCommandSink`; readiness metrics and would-command history. §§3, 11. |
| P2-R-018 Simulation cannot control equipment | Nonnegotiable 16 and 22; Master §15 | Deferred runtime; preserved invariant | Simulation is absent in Phase 2. Policy components remain pure and command sinks are injected so the Phase 7 Simulation Lab can use a separate input provider, virtual clock, namespace, and simulation-only sink. No simulation mode or endpoint can construct or arm a physical adapter or mutate live control. |
| P2-R-019 Diagnostics redaction | Nonnegotiable 20; Master §§1, 18 | Included | Phase 1 redaction expands to schedules, override, command, and UI health using allowlists/pseudonyms. §14. |
| P2-R-020 Full logging/reporting/in-interface activity | Architecture decision 2; Master §§17, 19, 21 | Included | Material decision/command/activity records, panel Activity route, events, entities, logs, and Repairs. §14. |

## 2.5 Traceability: weekly scheduling

| Requirement | Source | Disposition | Phase 2 interpretation and design location |
|---|---|---|---|
| P2-R-021 Visual weekly schedule per zone | Master §5; Phase 2 list | Included | One or more weekly profiles per zone with a core visual editor. §§5, 8. |
| P2-R-022 Multiple periods per day | Master §5 | Included | Ordered unique local start times; practical upper bound of 24 periods/day/profile. §5. |
| P2-R-023 Single target and separate heat/cool targets | Master §5 | Included | `TargetSpec` tagged union with capability-aware validation. §5. |
| P2-R-024 Comfort tolerance | Master §5 | Included | Per-period tolerance within configured bounds; affects semantic satisfaction, not predictive timing. §§5, 10. |
| P2-R-025 Copy a day | Master §5 | Included | Explicit copy operation with preview and optimistic concurrency. §8. |
| P2-R-026 Weekday/weekend templates | Master §5 | Included | Quick-start and bulk-apply operations that create ordinary day periods. §§5, 8. |
| P2-R-027 Sleep/Home/Away periods | Master §5 | Clarified | Period labels are included; occupancy may select matching weekly profiles or offsets. §§5, 13. |
| P2-R-028 Temporary exceptions | Master §5 | Included, limited | Implemented through manual overrides in Phase 2. Date-specific schedule exceptions are Phase 7. §§7, 8. |
| P2-R-029 Vacation schedules | Master §5 | Included, limited | Vacation occupancy mode can select a vacation weekly profile. Calendar/date-range vacation authoring is Phase 7. §13. |
| P2-R-030 Date-specific exceptions | Master §5 | Deferred | Phase 7 advanced editor. |
| P2-R-031 Schedule enable/disable | Master §5 | Included | Per-profile and per-zone enablement; disabling never changes the thermostat and leaves the zone in user-selected Manual Control or Observe Only. §§5, 8–9. |
| P2-R-032 Schedule preview | Master §5 | Included | Backend returns effective periods/transitions for a requested local week without changing runtime. §§5, 8. |
| P2-R-033 Predicted start/time-to-target/confidence | Master §5 | Deferred | Requires Phase 3/4 model contracts. UI omits values instead of showing placeholders. |
| P2-R-034 Before first/after last/empty day behavior | Master §5 | Included and clarified | Circular inheritance from the most recent period; at least one enabled weekly period. §§5–6. |
| P2-R-035 Separate backend/frontend components | Master §5 | Included | Independent TypeScript frontend package consuming supported WebSocket/entity/action contracts. §4. |
| P2-R-036 Card visual configuration editor | Master §5; Phase 7 list | Included, limited | Phase 2 editor covers entry, zone, density, and control visibility. Advanced layout/styling is Phase 7. §8. |
| P2-R-037 DST transitions | Master §22 | Included | Deterministic gap/fold policy and transition ledger. §6. |
| P2-R-038 Midnight/week boundary | Master §22 | Included | Circular weekly evaluator and strict-future transition calculation. §6. |
| P2-R-039 Schedule persistence/migration | Master §20 | Included | Separate authoritative atomic Schedule Store with schema and revision. §§5, 15. |
| P2-R-040 Schedule import/export | Master §20 | Deferred | Phase 7, with schema reserved now. |

## 2.6 Traceability: overrides, windows, occupancy, shared equipment, and fan

| Requirement | Source | Disposition | Phase 2 interpretation and design location |
|---|---|---|---|
| P2-R-041 Detect external controlled-value changes | Master §4 | Included | Target/range/mode/preset/fan/hold changes are correlated; uncertain changes are external. §§7, 11. |
| P2-R-042 Option: all external changes count | Master §4 | Included | Default true; when false, only attributable wall/device/user changes qualify and uncertain changes still suspend rather than counter-command. §7. |
| P2-R-043 Stop schedule correction during override | Nonnegotiable 3; Master §4 | Included | Override owns the target layer; no schedule target command until expiry/cancel. §§7, 9. |
| P2-R-044 Override source/start/expiry visible | Nonnegotiable 4; Master §4 | Included | Panel, climate attributes, sensors, activity, and diagnostics. §§7, 14. |
| P2-R-045 Cancel or extend override | Master §4 | Included | UI and actions with validated policy replacement. §§7, 14. |
| P2-R-046 Expire at next setpoint transition | Master §4 | Included | Next material effective schedule target change. §7. |
| P2-R-047 Expire after duration | Master §4 | Included | Persisted UTC expiry derived from bounded duration. §7. |
| P2-R-048 Expire at occupancy transition | Master §4 | Included | Next accepted debounced occupancy-mode transition. §7. |
| P2-R-049 Expire at clock time | Master §4 | Included | Next local occurrence with DST policy. §7. |
| P2-R-050 Until manually canceled | Master §4 | Included | No automatic expiry; safety and admin pause still dominate. §7. |
| P2-R-051 Until next day’s schedule begins | Master §4 | Included and clarified | First configured boundary on the next local date; midnight fallback if that date has no boundary. §7. |
| P2-R-052 Default expiry is next transition | Master §4 | Included | Applies to UI-created and newly detected external overrides unless user selects another policy. §7. |
| P2-R-053 Window/door assignment and different behavior | Nonnegotiable 6; Master §9 | Included | Typed bindings distinguish window/exterior door and carry policy. §12. |
| P2-R-054 Open/close debounce, grace, minimum duration, resume delay | Master §9 | Included | One deterministic contact state machine per binding. §12. |
| P2-R-055 Per-zone and whole-group suspension | Master §9 | Included | Shared command-authority groups escalate configured zone suspension to group suspension. §§12, 16. |
| P2-R-056 Left-open notification/reminders | Master §9 | Included | Persistent notification/activity with optional bounded repeat. §12. |
| P2-R-057 Temperature protection overrides window suspension | Master §9 | Included | Optional protection layer outranks suspension but still passes hard command gates. §§9–10, 12. |
| P2-R-058 Occupancy sources and modes | Master §13; Phase 2 list | Included | Person/tracker/binary/alarm/input/select mappings; Home/Away/Sleep/Vacation/Guest/custom. §13. |
| P2-R-059 Arrival/departure delays | Master §13 | Included | Deterministic, separately configurable timers; source reason retained. §13. |
| P2-R-060 Occupancy schedule or offset | Master §13 | Included | Exclusive per-zone effect; bounded offsets; selected zones. §13. |
| P2-R-061 Suspend predictive/precondition | Master §13 | Deferred as no-op metadata | Predictive behavior does not exist. Schema reserves future policy; no Phase 2 command depends on it. |
| P2-R-062 Explain occupancy source | Master §13 | Included | Decision reason, UI mode detail, activity, and diagnostics. §§13–14. |
| P2-R-063 Explicit shared conflict resolution | Master §2; user request | Included, limited | Single command authority, priority ordering, compatible-demand arbitration, conflict hold. §16. |
| P2-R-064 Basic fan control | Phase 2 list; Master §12 | Included | Selected circulation fan or supported thermostat fan mode only. §17. |
| P2-R-065 Fan spread/deviation/occupancy/time/season | Master §12 | Included, limited | Spread, occupancy, schedule/quiet periods, and optional heating-only/cooling-only enablement. Seasonal inference is user policy, not learned. §17. |
| P2-R-066 Humidity/dew-point/post-cooling lockout | Nonnegotiable 15; Master §12 | Included | Aggregated humidity and calculated dew point gate fan start; elevated humidity blocks post-cooling circulation. §17. |
| P2-R-067 Fan minimum on and hourly maximum | Master §12 | Included | Monotonic runtime budget and safe restore behavior. §17. |
| P2-R-068 Humidifier/dehumidifier/ventilation coordination | Master §12 | Deferred | Phase 6. |

## 2.7 Traceability: UI, entities, actions, data, and quality

| Requirement | Source | Disposition | Phase 2 interpretation and design location |
|---|---|---|---|
| P2-R-069 Professional sidebar interface | User request; Master §19 | Included | Responsive panel with progressive disclosure and accessible workflows. §8. |
| P2-R-070 Basics first: settings/status/sensors/climate/weather | User request | Included | Overview shows current climate, health, active settings summary, and weather observation; weather never controls Phase 2. §8. |
| P2-R-071 Direct control and scheduling | User request | Included | Safe Manual Control with automation off, safe overrides during scheduled operation, cancel/extend, schedule edit, and shadow/control management. §8. |
| P2-R-072 Complex settings available | User request; architecture decision 1 | Included for Phase 2 scope | Advanced accordion/settings routes expose all Phase 2 policies. Future-phase settings appear only when implemented. §8. |
| P2-R-073 Current and historical data | User request; Master §19 | Included, limited | Current snapshots, bounded 48-hour presentation trace, bounded activity/decision/command history, and Recorder-backed public entity history. Model/performance history deferred. §§8, 14–15. |
| P2-R-074 Cards for other dashboards | User request | Included | Zone control/status card and schedule/next-transition card. §8. |
| P2-R-075 Appropriate entities; avoid noise | Master §18 | Included | Small exact matrix; diagnostic detail disabled by default; no future placeholders. §14. |
| P2-R-076 Actions for pause/resume/override/cancel/force | Master §21 | Included | Registered in `async_setup`, translated errors, validated target entry/zone. §14. |
| P2-R-077 Events for override/schedule/window/fallback/command | Master §21 | Included | One documented typed event plus existing activity event. §14. |
| P2-R-078 Versioned persistence for schedule/override/journal | Master §20 | Included | Authoritative Schedule Store plus runtime schema v2. §§5, 15. |
| P2-R-079 Bounded writes and Recorder growth | Master §20 | Included | Debounced atomic writes, semantic entity updates, bounded histories, disabled diagnostics. §§14–15. |
| P2-R-080 Local-first | Master objective/§20 | Included | No new cloud/network dependency; all decisions local. §4. |
| P2-R-081 Comprehensive tests/docs | Nonnegotiable 21; Master §§1, 22 | Included | Deterministic unit/integration/frontend/contract/migration/HA walkthrough gates. §19. |
| P2-R-082 >95% coverage and complete flows | Master §22 | Included | ≥95% line and branch; 100% config/options/reconfigure and safety-state branches. §19. |
| P2-R-083 No private APIs | Master §1 | Included | Public config entries, entity APIs, actions, WebSocket extension, `panel_custom`, frontend static registration, and Recorder-supported APIs only. §§4, 8. |
| P2-R-084 Estimated versus measured truthfulness | Nonnegotiable 19 | Included | Dew point is labeled calculated; no efficiency, stage, energy, or prediction claims. §§14, 17. |
| P2-R-085 Interactive isolated Simulation Lab | Master §§15, 19, 23; architecture decision 3 | Deferred runtime; architecture reserved | Phase 7 provides virtual thermostat/indoor/outdoor/weather/contact/occupancy/equipment inputs, time controls, deterministic scenarios, faults, replay, and decision visualization. Phase 2 establishes only pure-policy and injected-sink boundaries. §§3–4, 8. |
| P2-R-086 Opt-in psychrometric comfort targeting | Master §6 and Phase 4; nonnegotiable 23; architecture decision 4 | Deferred | Phase 4 may adjust adaptive timing and derive a bounded effective temperature target. Feature-off, invalid/stale input, or insufficient confidence preserves the ordinary schedule. Phase 6 owns active humidity equipment. |
| P2-R-087 Automation-off visibility and Manual Control | Master §§2–3, 23–24; nonnegotiable 24; architecture decision 5; user request | Included | All observation/status surfaces remain available. Manual Control accepts only explicit user intents and applies capability, ownership, absolute-limit, correlation, acknowledgement, and failure gates without any autonomous trigger. §§3–4, 8–11, 14, 18–20. |
| P2-R-088 Observation for later thermal learning | Master §§7, 19, 20, 23; nonnegotiable 25; architecture decision 6; user request | Included, limited | Observe Only runs indefinitely with zero commands and preserves live/Recorder-compatible visibility plus bounded activity. Phase 3 adds model-ready observation storage, learned thermal properties, confidence, export, and analysis; Phase 2 makes no model claims. §§3, 8, 14, 19, 22. |
| P2-R-089 Progressive truthful visualization | Master §§16, 19, 23–24; nonnegotiable 26; architecture decision 7; user request | Included, limited | Phase 2 Today timeline shows only factual observed/configured/current-state series and material annotations. Predicted, planned, model, and simulation overlays appear only in their assigned later phases. §§8, 14–15, 19–22. |
| P2-R-090 Fact-grounded narrative | Master §§16, 19, 23–24; nonnegotiable 27; architecture decision 8; user request | Included, limited | Phase 2 provides a deterministic current-status explanation from snapshot/decision facts. Phase 3 adds learning hindsight and Phase 4 adds predictive daily plan/after-action narratives. No narrative layer can invent facts or influence commands. §§4, 8, 14, 19–22. |

# 3. Phase transition and safety invariant

## 3.1 Replaced Phase 1 invariant

Phase 1 invariant:

> For every event, configuration, restart condition, entity state, and user interaction, Phase 1 emits zero Home Assistant service calls that can change physical climate equipment.

Phase 2 replaces it with:

> A physical climate action may be emitted only through the single active command adapter and under one of two authorities: (a) Scheduled Control, after mandatory shadow qualification and every autonomous-control gate; or (b) Manual Control, from a current explicit user action and never from a sensor, schedule, timer, occupancy, contact, fan policy, restart, or learned/predictive event. In either case the complete command must be capability-valid, ownership-valid, finite, bounded by absolute limits, correlated to the latest observed precondition, outside applicable dedupe/interval/cooldown rules, and journaled before dispatch. Every other proposed command is suppressed and recorded without a physical action.

Additional invariants:

1. Observe Only and Scheduled Shadow always produce zero physical actions.
2. Disabled and Emergency Pause always produce zero physical actions.
3. Manual Control never produces an autonomous physical action; each command has a fresh authenticated user intent and no automatic target reassertion.
4. Turning off schedules and intelligent features never removes observation, status, history, activity, diagnostics, or deliberate Manual Control.
5. A schedule, UI override, manual command, occupancy offset, fan policy, restart, unavailable sensor, conflicting zone, or retry can never bypass `SafetyGate`.
6. A command is never inferred as successful from action-call completion alone.
7. An uncertain command outcome suppresses further commands to that thermostat until reconciliation or administrator acknowledgement.
8. An external thermostat change is never immediately counter-commanded.
9. Loss/unload/crash of Intelligent Climate sends no cleanup or “restore” command.
10. The original thermostat remains independently usable at all times.
11. A control mode restored from storage is an intent to re-arm after reconciliation, not permission to command during startup.
12. Only one entry-scoped adapter owns a thermostat because cross-entry ownership remains forbidden.

## 3.2 Operating stages

| Stage | Physical commands | Entry condition | Exit condition |
|---|---:|---|---|
| Disabled | No | Administrator disables the integration control plane or a blocking setup fault exists | Administrator selects Observe Only or Manual Control after reconciliation |
| Observe Only | No | Default after migration/new setup or user selects observation | User selects Manual Control or starts Scheduled Shadow |
| Manual Control | Explicit user commands only, gated | User turns autonomous control off but retains interface control | User selects Observe Only, starts Shadow, disables, or pauses |
| Scheduled Shadow — qualifying | No | Valid schedules and control bindings | Readiness thresholds pass |
| Scheduled Shadow — ready | No | Qualification complete | Administrator explicitly arms control |
| Scheduled Control | Yes, gated | Confirmation plus every gate passes | Pause, failure, external override, suspension, degraded data, or mode change |
| Manual Override | Only the initial safe UI override command; no schedule correction | UI override or external change while scheduled control owns the target | Expiration/cancel; then reconciliation |
| Safe Fallback | No by default | Required input/capability/command is unsafe or uncertain | Two healthy evaluations plus applicable cooldown/ack |
| Emergency Protection | Optional, gated | User-enabled protection threshold and trustworthy observation | Protected band restored with hysteresis |
| Emergency Pause | No | User/admin action or blocking command fault | Explicit administrator resume after reconciliation |

# 4. Architecture and repository changes

## 4.1 Component architecture

The coordinator remains the event-driven orchestration owner. Phase 2 adds pure schedule, override, occupancy, contact, arbitration, safety, and command-planning delegates. Physical actions are isolated behind a small adapter; no policy module receives `HomeAssistant.services`.

Data flow:

1. A state report, schedule deadline, override deadline, occupancy/contact timer, explicit user command, UI mutation, or startup event identifies affected zones.
2. Observation/capability evaluation produces the same trusted Phase 1 inputs.
3. In Manual Control, an explicit user intent goes directly to manual command planning and every autonomous policy path is marked inapplicable. Otherwise, schedule evaluation computes the current base target and next material transition.
4. Occupancy applies a selected profile or bounded offset.
5. Override, contact suspension, protection, and master state establish precedence.
6. Shared-equipment arbitration produces at most one group command plan per evaluation.
7. `SafetyGate` validates the full plan against current observations, capabilities, absolute limits, deadbands, intervals, cooldowns, correlation state, and shadow/control mode.
8. The selected sink records suppression or invokes the physical adapter.
9. The acknowledgement tracker correlates later state changes.
10. One immutable snapshot updates entities, frontend subscriptions, activity, diagnostics, and bounded persistence.

## 4.2 Proposed repository changes

```text
custom_components/intelligent_climate/
├── __init__.py                         # mode-safe setup, migrations, action registration hook
├── const.py                            # Phase 2 platforms/events/action names
├── coordinator.py                      # orchestration only; no policy algorithms
├── runtime.py                          # entry-scoped service composition
├── websocket.py                        # typed read/write frontend API
├── frontend.py                         # static URL and sidebar panel lifecycle
├── climate.py                          # conditionally writable virtual zone climate
├── sensor.py
├── binary_sensor.py
├── switch.py
├── select.py                           # operating mode/profile where appropriate
├── button.py                           # cancel override/emergency pause acknowledgement
├── diagnostics.py
├── repairs.py
├── storage.py                          # runtime Store v2
├── schedule_storage.py                 # authoritative Schedule Store v1
├── presentation_trace.py               # bounded nonauthoritative 48-hour UI trace
├── timeline.py                         # canonical provenance-labeled timeline DTO
├── narrative.py                        # deterministic fact-packet formatter; no authority
├── actions.py                          # registered once from async_setup
├── translations/en.json
├── services.yaml
├── models/
│   ├── schema.py                       # config/options/zone/runtime migrations
│   ├── schedule.py
│   ├── control.py
│   ├── override.py
│   ├── occupancy.py
│   ├── contact.py
│   ├── command.py
│   ├── presentation.py
│   └── frontend.py
├── schedule/
│   ├── validate.py
│   ├── evaluate.py
│   ├── transitions.py
│   └── time.py
├── control/
│   ├── state_machine.py
│   ├── precedence.py
│   ├── arbitration.py
│   ├── safety.py
│   ├── manual_control.py                # explicit user-intent planning only
│   ├── command_planner.py
│   ├── command_sink.py
│   ├── command_adapter.py
│   ├── acknowledgement.py
│   └── reasons.py
├── override/
│   ├── state_machine.py
│   ├── correlation.py
│   └── expiration.py
├── environment/
│   ├── contacts.py
│   ├── occupancy.py
│   └── fan.py
└── frontend_dist/                      # release-built immutable JS/CSS assets

frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── panel/
│   ├── cards/
│   ├── editors/
│   ├── api/
│   ├── components/
│   │   └── climate-timeline/
│   ├── state/
│   ├── styles/
│   └── types/
├── test/
└── dist/                               # copied to frontend_dist only at release build

tests/
├── unit/
│   ├── test_schedule_*.py
│   ├── test_override_*.py
│   ├── test_control_*.py
│   ├── test_arbitration.py
│   ├── test_safety.py
│   ├── test_contacts.py
│   ├── test_occupancy.py
│   ├── test_fan.py
│   ├── test_presentation_trace.py
│   ├── test_timeline.py
│   ├── test_narrative.py
│   └── test_command_*.py
├── integration/
│   ├── test_shadow_gate.py
│   ├── test_manual_control.py
│   ├── test_active_control.py
│   ├── test_restart_control.py
│   ├── test_schedule_websocket.py
│   ├── test_timeline_websocket.py
│   ├── test_actions.py
│   ├── test_entities_phase_2.py
│   ├── test_migration_phase_2.py
│   └── test_failure_matrix.py
├── frontend/
└── acceptance/
```

## 4.3 Dependency rules

- `models`, schedule evaluation, state machines, precedence, arbitration, and safety are pure Python and do not import Home Assistant services.
- `command_adapter.py` is the only module allowed to invoke `hass.services.async_call`.
- `command_sink.py` selects Observe, Shadow, Manual-Active, or Scheduled-Active behavior through dependency injection; both active compositions share one adapter and safety gate but have distinct authority predicates.
- `manual_control.py` accepts only authenticated, current user intents. It cannot subscribe to sensors, schedules, deadlines, contacts, occupancy, learning, forecasts, or restart callbacks.
- Input providers, clocks, state namespaces, and command sinks remain explicit dependencies. A future simulation composition root can therefore reuse pure policy modules without importing or constructing `command_adapter.py`.
- `presentation_trace.py`, `timeline.py`, and `narrative.py` may consume immutable snapshots/activity/model fact packets but are forbidden dependencies of schedule, control, safety, arbitration, command planning, qualification, and learning modules.
- Narrative rendering is a pure output operation. It cannot mutate state, dispatch an action, lower a gate, or add facts not present in its validated packet.
- Frontend assets do not read `.storage`, config-entry internals, or Python objects.
- Backend writes remain authoritative; frontend previews may never become runtime control data until backend validation and atomic persistence succeed.
- All frontend/backend payloads are explicitly versioned and validated.

# 5. Weekly schedule model, validation, precedence, and persistence

## 5.1 Authoritative schedule document

Schedules are required user configuration but are too large and independently versioned to place in config-entry options. They use a separate authoritative Store:

- Key: `intelligent_climate.schedule.<entry_id>`
- Home Assistant Store envelope: version 1.0
- Inner schema: `schedule_schema_version: 1`
- Atomic writes: required
- Optimistic revision: monotonically increasing integer
- Write behavior: validate complete document, write once, then publish
- Runtime behavior on failure: keep last validated in-memory document if already running; otherwise Observe Only and a Repair

Conceptual model:

```text
ScheduleDocument
  schedule_schema_version: 1
  entry_id: str
  equipment_group_id: UUID
  time_zone: IANA zone name
  revision: int
  zones: map[ZoneId, ZoneScheduleSet]
  saved_at_utc: datetime

ZoneScheduleSet
  zone_id: UUID
  enabled: bool
  selected_profile_id: ScheduleProfileId
  profiles: tuple[WeeklyScheduleProfile, ...]

WeeklyScheduleProfile
  profile_id: UUID
  name: str
  enabled: bool
  days: map[Weekday, tuple[SchedulePeriod, ...]]

SchedulePeriod
  period_id: UUID
  local_start: LocalTime
  label: str
  occupancy_label: HOME | AWAY | SLEEP | VACATION | GUEST | CUSTOM | NONE
  target: TargetSpec
  tolerance_c: float

TargetSpec
  kind: SINGLE | RANGE
  target_c: float | None
  heat_target_c: float | None
  cool_target_c: float | None
```

Schedule and period UUIDs survive rename, copy, and ordinary edits. Copying a day creates new period IDs to prevent one edit from mutating two days.

## 5.2 Validation

Backend validation is authoritative and rejects the complete write if any condition fails:

1. Document identity must match the loaded entry/group.
2. Time zone must equal the current acknowledged Home Assistant IANA time zone.
3. Every configured zone has exactly one schedule set; no unknown zones exist.
4. Profile IDs and period IDs are unique within the entry.
5. Profile names are nonblank and unique per zone after case folding.
6. Every local start is minute-precision `00:00` through `23:59`.
7. A day contains at most 24 periods and no duplicate start time.
8. Periods are stored and encoded in ascending local start order.
9. An enabled selected profile contains at least one enabled period in the week.
10. Every value is finite and stored in Celsius.
11. A single target is supported by the command-authority thermostat.
12. A range target is supported by the thermostat, or the UI must convert it to an explicitly selected single-mode strategy before saving.
13. User absolute limits, thermostat advertised limits, and minimum heat/cool separation all pass.
14. Tolerance is between 0.1°C and 2.8°C.
15. Labels are bounded plain text and contain no markup.
16. Profile selection referenced by occupancy policies must exist.
17. A schedule revision update must match the caller’s `expected_revision`.

Validation returns field-addressable errors for the UI and a concise entry-level category for logs/Repairs. It never partially saves valid days from an invalid document.

## 5.3 Effective-target precedence

The target pipeline is ordered:

1. Base weekly profile and period.
2. Accepted occupancy profile selection or bounded offset.
3. Explicit forced period, represented as a manual override.
4. Manual override target.
5. Optional emergency temperature-protection target.
6. Absolute/user/thermostat capability clamp and validation.

Window suspension does not produce another target; it suppresses ordinary comfort command execution. Disabled, Emergency Pause, reconciliation, command uncertainty, or unavailable required data suppress the plan after target calculation so the UI can still explain the would-be target.

## 5.4 Schedule evaluation

Evaluation is a pure function of:

- validated schedule document;
- zone/profile selection;
- timezone-aware evaluation instant;
- accepted occupancy mode;
- active override/protection state; and
- immutable configuration limits.

It returns:

```text
ScheduleEvaluation
  base_period_id
  base_target
  effective_target
  current_local_date/time/fold
  inherited_from_previous_day: bool
  next_boundary_utc
  next_material_transition_utc
  next_material_target
  reason_code
```

The coordinator owns one earliest-deadline timer across schedule, override, contact, occupancy, retry, cooldown, and fan deadlines. It does not poll each minute.

## 5.5 Persistence consistency

Schedule writes use compare-and-swap revision semantics. The panel submits the complete edited zone schedule plus `expected_revision`; the backend validates it against the current full document, writes an incremented revision atomically, and returns the canonical result. A stale editor receives a conflict and must reload before resubmitting.

Active control evaluates only the last successfully loaded canonical document. An unsaved browser draft has no runtime effect.

# 6. Time-zone, DST, midnight, and week-boundary behavior

## 6.1 Clock model

- Persisted deadlines and command timestamps use UTC.
- Weekly period definitions use local wall-clock weekday and minute.
- Rendering uses Home Assistant’s configured time zone.
- Tests use timezone-aware deterministic clocks and `zoneinfo`.
- Naive datetimes are rejected at every boundary.

## 6.2 Spring-forward gap

If a configured time does not exist:

- The transition is assigned to the first valid local instant after the gap.
- All transitions in the skipped interval are evaluated in configured order at that instant.
- Only the final effective material target creates a command plan.
- The transition ledger records each boundary as processed, avoiding a burst.

Example: Sunday periods at 02:10 and 02:40 during a 02:00–03:00 gap are both processed at 03:00; if they produce different targets, only the 02:40 effective result is eligible for one command.

## 6.3 Fall-back fold

If a configured time occurs twice:

- The transition occurs at the first occurrence (`fold=0`).
- The repeated wall-clock occurrence does not trigger another transition.
- A persisted key `(zone_id, profile_id, period_id, local_date)` prevents duplicate execution across restart.

The current period during the second occurrence remains the result established at the first occurrence.

## 6.4 Midnight and empty days

- A period remains effective until another material target transition.
- At 00:00 there is no synthetic transition unless a period starts at 00:00.
- Before a day’s first period, search backward through prior days for the most recent period.
- A day with no periods inherits the prior active period.
- After the final period on Sunday, it remains active into Monday until Monday’s next period.
- If the entire selected week has no enabled period, the schedule is invalid and cannot be armed.

## 6.5 Time-zone changes

On Home Assistant time-zone change:

1. Cancel local-time deadlines.
2. Suppress active commands.
3. Record `time_zone_changed`.
4. Enter Scheduled Shadow/Reconciliation.
5. Re-render the schedule in the new zone for administrator review.
6. Require explicit acknowledgement, update the schedule document time zone, reset shadow qualification, and restart qualification.

# 7. Manual-override design

## 7.1 Override model

```text
ManualOverride
  override_id: UUID
  zone_id: UUID
  scope: TARGET | HVAC_MODE | FAN_MODE | PRESET | HOLD | MULTI_VALUE
  source: INTELLIGENT_CLIMATE_UI | PHYSICAL_OR_EXTERNAL | HA_USER | HA_AUTOMATION | UNKNOWN
  source_context_id: str | None
  requested_values: allowlisted typed values
  started_at_utc: datetime
  last_updated_at_utc: datetime
  expiration_policy: OverrideExpirationPolicy
  expires_at_utc: datetime | None
  anchor_transition_key: str | None
  state: ACTIVE | EXPIRING | ENDED
  end_reason: enum | None
```

Override state is persisted in runtime Store v2. Raw context/user identifiers are not copied into diagnostics or event payloads.

## 7.2 Detection

The correlation engine compares a thermostat change with:

- command target entity and controlled fields;
- command issue and acknowledgement windows;
- Home Assistant context ID and parent ID when available;
- pre-command state;
- normalized desired result;
- observed update ordering; and
- pending/acknowledged command journal entries.

Classification order:

1. Exact pending-command semantic match: acknowledge the command.
2. Late exact match to the most recent acknowledged command with no intervening external change: correlated Intelligent Climate change.
3. Explicit different user/context and controlled-value change: external override.
4. Controlled-value change with missing/ambiguous origin: external override when `all_external_changes_are_overrides=true`; otherwise enter uncertain-control suspension and ask the user rather than counter-command.
5. Uncontrolled attribute or telemetry-only change: observation, not override.

## 7.3 State transitions

| Current | Trigger | Next | Command behavior |
|---|---|---|---|
| None | Safe UI override | Active | One validated command; schedule correction suppressed |
| None | External controlled change | Active | No command |
| Active | Another external controlled change | Active updated | No command; expiration recalculated by selected policy |
| Active | Extend | Active updated | No command unless target also changes |
| Active | Cancel | Expiring | Reconcile; no immediate catch-up burst |
| Active | Expiry deadline/transition | Expiring | Reconcile current thermostat and schedule |
| Expiring | Thermostat already equals effective schedule | Ended | No command |
| Expiring | Mismatch attributable to the override and all gates pass | Ended | At most one schedule command after cooldown |
| Expiring | Mismatch origin uncertain/external | Active renewed or Safe Fallback | No command |
| Any | Protection | Remains recorded under protection | Only protection plan may execute |
| Any | Pause/Disabled/uncertain command | Retained, execution suppressed | No command |

## 7.4 Expiration policies

1. **Next scheduled setpoint transition:** next strict-future effective scheduled target change after occupancy effects; same target does not count.
2. **Duration:** 15 minutes through 7 days; store one UTC deadline.
3. **Next occupancy transition:** next accepted debounced mode change, excluding initial startup resolution and source bounce.
4. **Specified clock time:** next occurrence in the configured local time zone; if already passed, use the next local day; apply DST gap/fold rules.
5. **Until manually canceled:** no deadline.
6. **Next day’s schedule begins:** first configured period boundary on the next local date; if that date has no boundary, expire at next local midnight so inherited schedule resumes predictably.

The UI always shows an exact local expiration description and UTC-backed timestamp where one exists.

# 8. Schedule UI and backend/frontend boundary

## 8.1 Information architecture

The sidebar title is **Intelligent Climate**. Its primary routes:

1. **Overview** — group status, control stage, automation status, shadow readiness, zone summaries, thermostat action, targets, sensor health, weather observation, open contacts, occupancy, warnings, next transition, the Today climate timeline, and a concise fact-grounded current-status explanation. It remains fully populated in Observe Only and Manual Control.
2. **Schedule** — zone/profile selector, weekly editor, current-period marker, validation summary, copy/template tools, and preview.
3. **Control** — an explicit mode selector for Observe Only, Manual Control, and scheduled Shadow/Control workflows; safe manual target/mode/fan controls; temporary override and expiration controls when scheduled; pause/resume; shadow qualification; active-control confirmation; and command status.
4. **Sensors** — included/excluded sources, freshness, calibration summary, contacts, occupancy, fan inputs, and weather availability.
5. **Activity** — filterable material timeline for decisions, transitions, overrides, suspensions, commands, acknowledgements, failures, Repairs, and lifecycle.
6. **Settings & Diagnostics** — progressive sections for schedules, safety limits, command timing, contacts, occupancy, fan, shared authority, source health, activity retention, diagnostics download, and Repairs links.

Future routes appear only when implemented. The Phase 2 UI does not display fake model confidence, indoor-temperature predictions, planned predictive actions, performance, energy, psychrometric comfort, or simulation values. It may show an available outdoor weather forecast only as clearly labeled context and explicitly states that forecast does not influence Phase 2 control. Phase 7 adds a dedicated **Simulation Lab** route rather than changing the live Control route into a simulator.

## 8.2 UX rules

- Status precedes configuration.
- The top-level banner always states one of: Observe Only, Manual Control — Automation Off, Shadow Qualifying, Shadow Ready, Scheduled Control, Override, Suspended, Safe Fallback, Emergency Protection, or Paused.
- Turning automation off never blanks or hides status. The interface explicitly says that schedules, occupancy/window actions, learned/predictive behavior, and automatic fan circulation are inactive while manual controls and observation remain available.
- Manual Control actions are visually labeled **Apply now** and never masquerade as a schedule or expiring override. Observe Only presents the same information but replaces controls with a clear **Switch to Manual Control** action.
- Dangerous actions require plain-language confirmation describing which physical thermostat can change.
- Active Control cannot be armed from a generic toggle; it uses a readiness checklist and explicit confirmation.
- Advanced settings are collapsed but searchable and include recommended values and unit-aware help.
- Schedule errors appear beside the affected day/period and in a summary.
- Unsaved edits are visibly distinct; leaving with edits prompts save/discard.
- Every timeline series and narrative fact is labeled by provenance: measured, configured, calculated, forecast, predicted, or planned. Phase-inapplicable and unavailable series are omitted or explicitly marked unavailable, never rendered as zero.
- Chart meaning does not depend on color. Line style, markers, labels, legend text, focusable annotations, a tabular/screen-reader summary, and reduced-motion behavior carry the same information.
- Red, amber, blue, and green are never the only status signal; icons and text are required.
- Keyboard navigation, focus order, reduced motion, 44-pixel touch targets, responsive 320-pixel layouts, and WCAG AA contrast are release gates.
- Cards and panel use Home Assistant themes and locale/unit formatting.

## 8.3 Phase 2 weekly editor

Desktop uses a seven-column weekly view with a synchronized period list. Mobile uses one day at a time. Users can:

- add, edit, duplicate, and delete periods;
- edit time, label, occupancy label, target/range, and tolerance;
- copy a day to selected days;
- apply weekday/weekend starter templates;
- enable/disable a zone/profile;
- select a profile;
- preview current and next effective targets;
- see inherited periods on empty-day/before-first areas; and
- view exact DST warnings for the previewed week.

The editor shows the current aggregate command-authority HVAC mode and
advertised single/range target capabilities without exposing thermostat entity
IDs. A single target is control-compatible only in an unambiguous Heat or Cool
mode; a range is control-compatible only in Heat/Cool or Auto. Off,
unavailable, and incompatible combinations remain editable and visible but
fail closed before a Shadow or active plan. The schedule never changes HVAC
mode implicitly; mode selection remains an explicit Control-route workflow.

The core editor does not require drag-and-drop. Phase 7 may add it as an alternate interaction, not replace the accessible form/list path.

## 8.4 Today climate timeline and narrative

The Overview route and zone detail view include a local-day timeline that remains useful in Observe Only and Manual Control. All timestamps are transferred as UTC instants and labeled in the Home Assistant time zone. A 23-hour or 25-hour DST day is drawn at its actual duration; repeated local-hour labels include the offset or fold marker.

Phase 2 series and annotations:

- measured effective zone temperature as a solid line;
- configured scheduled target as a step line;
- effective target as a separate step line when an override, occupancy offset, safety overlay, or control suppression makes it differ from schedule;
- measured outdoor temperature and available weather observations on a clearly labeled secondary scale;
- available forecast outdoor temperature as a dashed context-only series that never feeds Phase 2 command logic;
- actual thermostat HVAC action and fan action as non-temperature state bands;
- current-time cursor and schedule-transition markers; and
- material annotations for overrides, occupancy changes, contact suspension/resume, fallback, pause, command attempt/acknowledgement/failure, and sensor/weather degradation.

Phase 2 deliberately omits predicted indoor temperature, confidence bands, predicted arrival, predictive start/stop/coast intervals, and model-adjustment claims. The legend states **No indoor prediction in Safe Scheduled Control**. This is a truthful capability boundary, not an empty placeholder.

The backend returns a canonical timeline DTO. Every series carries `value_kind` (`measured`, `configured`, `calculated`, `forecast`, `predicted`, or `planned`), unit, source-quality state, start/end coverage, and missing-data intervals. Every annotation carries a typed reason and stable activity reference. The frontend selects density and presentation but does not recalculate targets, infer causes, join events heuristically, or relabel provenance.

To make the current day available without depending on Recorder configuration, a separate nonauthoritative **Presentation Trace Store v1** retains:

- a maximum of 48 rolling hours per zone;
- five-minute rounded observation buckets, plus immediate points for material target, equipment-state, quality, or control-event changes;
- effective zone temperature/humidity, outdoor observation, scheduled/effective target, thermostat/fan action, privacy-safe aggregate contact state, material control context, quality flags, and typed annotation references;
- no raw source attributes, user/context identifiers, free-form exception text, or executable command payloads;
- debounced persistence no more often than every 15 minutes plus orderly shutdown; and
- corruption, write failure, or loss degrades only historical display and raises the existing Store/diagnostic path; it never changes a control decision, qualification result, or command.

This trace is not training data and must never be read by the control, safety, schedule, prediction, or Phase 3 learning engines. Phase 3 creates a separate model-ready observation store with its own provenance and quality contract. Recorder remains the optional source for longer public-entity history.

Phase 2 also returns a short deterministic current-status fact packet and rendered explanation, for example: **“Cooling target is 74°F until 6:00 PM. The zone is 75.2°F and cooling is running. Outdoor forecast is shown for context and does not affect Safe Scheduled Control.”** Templates may describe current state, schedule, override, suspension, fallback, source quality, and the next transition only when those facts are present. The narrative formatter cannot dispatch commands, mutate state, lower a safety gate, or infer a weather/model cause.

Later phases extend the same schema without changing the meaning of existing series:

| Phase | Timeline additions | Narrative additions |
|---|---|---|
| 3 — Thermal Learning | Shadow-predicted indoor trajectory, confidence band, predicted arrival, residuals, and actual-versus-predicted error | Factual learning retrospective, including miss duration and only committed validated model updates |
| 4 — Predictive Control | Planned start/stop/coast intervals, projected target arrival, forecast/solar influence annotations, and actual-versus-plan comparison | Daily plan briefing and after-action explanation of recorded influences, confidence, fallback, and measured result |
| 7 — Frontend Completion | Interactive compare, zoom, replay, simulation overlays, scenario comparison, and advanced model/performance exploration | User-selectable detail and optional meaning-preserving language restyling |

## 8.5 Cards

**Zone card**

- current effective temperature/humidity;
- active and scheduled target;
- HVAC action and control stage;
- override/window/occupancy/sensor warning chips;
- next transition;
- optional safe target/mode/fan adjustment that creates a direct user command in Manual Control or a bounded manual override in Scheduled Control; and
- deep links to Control, Sensors, and Activity.

**Schedule card**

- current period/profile;
- today’s periods;
- next transition and target;
- schedule enabled/shadow/control state; and
- deep link to edit in the sidebar.

When scheduling is disabled, the Schedule card shows **Automation off** rather than an error and offers links to Manual Control and Observe Only. Neither card loses sensor or equipment-state visibility when automation is off.

The Phase 2 card editor allows entry, zone, compact/comfortable density, visibility of control buttons, displayed secondary metric, and an optional compact sparkline based on the same canonical factual presentation trace. Phase 7 owns layout composition, advanced chart comparison/interaction, colors, and extensive visual configuration.

## 8.6 Backend/frontend API

Versioned WebSocket commands:

- `intelligent_climate/config/get`
- `intelligent_climate/snapshot/get`
- `intelligent_climate/subscribe`
- `intelligent_climate/schedule/get`
- `intelligent_climate/schedule/validate`
- `intelligent_climate/schedule/save`
- `intelligent_climate/schedule/preview`
- `intelligent_climate/activity/list`
- `intelligent_climate/shadow/status`
- `intelligent_climate/observation/status`
- `intelligent_climate/timeline/today`
- `intelligent_climate/narrative/current`

Mutating control operations use documented Home Assistant actions so automations and the UI share validation:

- `intelligent_climate.pause_control`
- `intelligent_climate.resume_control`
- `intelligent_climate.set_operating_mode`
- `intelligent_climate.set_manual_target`
- `intelligent_climate.set_manual_hvac_mode`
- `intelligent_climate.set_manual_fan_mode`
- `intelligent_climate.set_temporary_override`
- `intelligent_climate.extend_override`
- `intelligent_climate.cancel_override`
- `intelligent_climate.force_schedule_period`
- `intelligent_climate.acknowledge_control_fault`

The frontend never computes the authoritative active period, expiration, safety clamp, command, timeline provenance, causal influence, or narrative fact. Every Manual Control mutation includes the current entry, zone, observed-state revision, and user context so the backend can reject stale or replayed intent. Preview, timeline, and narrative responses are explicitly nonauthoritative for control; schedule previews remain unsaved until confirmed.

# 9. Control and arbitration state machine

## 9.1 Control state

`ControlState` expands to:

```text
UNLOADED
INITIALIZING
RECONCILING
DISABLED
OBSERVING
MANUAL_IDLE
SHADOW_QUALIFYING
SHADOW_READY
SCHEDULED_IDLE
SCHEDULED_PENDING
COMMAND_AWAITING_ACK
MANUAL_OVERRIDE
WINDOW_SUSPENDED
OCCUPANCY_HOLD
SHARED_CONFLICT_HOLD
EMERGENCY_PROTECTION
SAFE_FALLBACK
EMERGENCY_PAUSED
DEGRADED
UNLOADING
```

Operating mode describes user intent; control state describes current execution. Occupancy is an overlay, not a mode that erases Scheduled Control.

## 9.2 Precedence

Highest to lowest:

1. Invalid configuration/migration or unsupported future schema.
2. Disabled or Emergency Pause.
3. Startup/reload reconciliation.
4. Thermostat unavailable, capability invalid, command awaiting/uncertain, or repeated failure lockout.
5. Manual Control explicit user intent, when that is the selected mode.
6. Required autonomous sensor invalidity.
7. Optional emergency temperature protection.
8. External/manual override during scheduled operation.
9. Window/door suspension.
10. Shared-equipment conflict hold.
11. Accepted occupancy profile/offset.
12. Weekly schedule.
13. Basic fan circulation as a secondary plan.

Protection cannot bypass an unavailable thermostat, unsupported command, uncertain prior command, Disabled, or Emergency Pause. Manual Control bypasses schedule, occupancy, window, protection, and automatic fan policy because none of those policies are active; it does not bypass ownership, capability, absolute limits, correlation, acknowledgement, failure lockout, or pause. Unavailable external zone sensors do not prevent a deliberate safe thermostat command in Manual Control, but their unavailability remains visible.

## 9.3 Transition discipline

- Every transition has a stable reason code.
- Illegal transitions go to Safe Fallback and record an invariant violation.
- A single evaluation may produce at most one thermostat plan and one fan plan per equipment group.
- Entering a suppressing state cancels retry/deferred-command timers but not observation or expiration timers.
- Leaving suppression reevaluates; it does not blindly execute the previously suppressed plan.
- Degraded-to-active recovery requires two healthy evaluations at least 30 seconds apart, plus any longer applicable command cooldown.

# 10. Absolute limits, intervals, deadbands, and cooldowns

## 10.1 Limit intersection

For every target:

```text
allowed target =
  finite numeric value
  ∩ thermostat advertised min/max
  ∩ user absolute heating/cooling limits
  ∩ valid mode/range capability
  ∩ user minimum heat/cool separation
```

There is no silent clamp for a saved schedule: invalid schedules are rejected. A direct manual command or UI override may offer to use the nearest safe value only after showing the adjusted result and obtaining confirmation.

Recommended initial values, displayed and confirmed during control setup:

- Minimum allowed heating target: 45°F (7.2°C)
- Maximum allowed heating target: 80°F (26.7°C)
- Minimum allowed cooling target: 60°F (15.6°C)
- Maximum allowed cooling target: 95°F (35.0°C)
- Minimum heat/cool separation: 3°F (1.7°C)
- Emergency low threshold: 45°F (7.2°C), target 50°F (10.0°C)
- Emergency high threshold: 90°F (32.2°C), target 85°F (29.4°C)

Home Assistant displays the user’s unit system; storage remains Celsius.

## 10.2 Timing defaults

| Protection | Default | Behavior |
|---|---:|---|
| Automatic command minimum interval | 300 seconds/thermostat | New plan suppressed until reevaluation at deadline; never queued blindly |
| Direct UI override minimum interval | 60 seconds/thermostat | One user command may preempt an automatic cooldown when safe; begins a new 300-second automatic cooldown |
| Manual Control command minimum interval | 2 seconds/thermostat | Reject duplicate/click-spam commands; no deferred execution or automatic reassertion |
| HVAC mode reversal cooldown | 900 seconds | Opposite mode plan suppressed; native thermostat remains in control |
| Target semantic deadband | 0.3°C (about 0.5°F) | No command when observed target is within deadband |
| Range endpoint deadband | 0.3°C each | Both endpoints must be materially different |
| Acknowledgement window | 30 seconds | State must match semantically |
| Retry delay | 30 seconds minimum | One retry only if all retry preconditions pass |
| Failure cooldown | 15 minutes | No automatic command after terminal failure |
| Repeated-failure lockout | 3 failures in 60 minutes | Emergency Pause/Repair until administrator acknowledgement |
| Startup quiet period | At least 120 seconds and full reconciliation | No physical command |

These supplement, never replace, thermostat-native compressor, stage, minimum-on, and minimum-off protections. Phase 2 does not claim to observe or enforce compressor cycling when the underlying thermostat does not expose it.

# 11. Command adapter, correlation, acknowledgement, retry, and failure

## 11.1 Command model

```text
CommandPlan
  command_id: UUID
  decision_id: UUID
  entry_id/group_id/zone_id
  target_entity_id
  command_kind: SET_TARGET | SET_RANGE | SET_HVAC_MODE | SET_FAN_MODE | FAN_ON | FAN_OFF
  desired: typed allowlisted payload
  observed_precondition: normalized semantic fingerprint
  cause: MANUAL_USER | SCHEDULE | UI_OVERRIDE | OVERRIDE_END | PROTECTION | FAN_POLICY
  authority: MANUAL | SCHEDULED
  user_context_id: required only for MANUAL_USER and UI_OVERRIDE
  created_at_utc
  not_before_utc
  expires_at_utc
  safety_evaluation_id
  dedupe_fingerprint
```

The journal record adds attempts, action context, service completion, acknowledgement, observed result, terminal status, and bounded reason. It never stores arbitrary Home Assistant attributes or exception text.

## 11.2 Adapter allowlist

The active adapter may call only:

- `climate.set_temperature`
- `climate.set_hvac_mode`
- `climate.set_fan_mode`
- `fan.turn_on`
- `fan.turn_off`

Only configured, owned thermostat/fan entities are valid targets. No templated domain/action name, arbitrary service data, or user-supplied action is permitted.

Where a thermostat supports combined `hvac_mode` and target in one `set_temperature` call, one action is preferred. If an ordered multi-action transaction is unavoidable, each step must acknowledge before the next. Partial failure stops the transaction and enters command uncertainty; there is no automatic rollback.

## 11.3 Sink behavior

- `ObserveOnlyCommandSink`: records a suppressed intent; physical call count must be zero.
- `ShadowCommandSink`: records a fully validated would-command result and qualification metrics; physical call count must be zero.
- `ManualActiveCommandSink`: accepts only a fresh explicit user intent while the entry is in Manual Control, revalidates manual authority and safety, writes a pending journal record, and invokes the adapter once. It has no event/timer subscription and never reasserts a command.
- `ScheduledActiveCommandSink`: revalidates Scheduled Control and a fresh safety token, writes a pending journal record, then invokes the adapter.

The scheduled active sink is constructed only after shadow qualification and explicit arming. The manual active sink may be constructed after configuration/ownership validation, startup reconciliation, and the user’s explicit selection of Manual Control; it does not require a schedule or shadow qualification. Merely restoring either active intent from storage does not construct a sink before reconciliation.

## 11.4 Acknowledgement

Acknowledgement requires a subsequent normalized state to match the controlled semantic fields:

- set target: target within deadband;
- set range: both endpoints within deadband;
- set HVAC mode: exact mode;
- set thermostat fan mode: exact normalized fan mode;
- fan on/off: exact state.

Unrelated attribute updates do not acknowledge. A context match strengthens correlation but cannot replace semantic matching.

## 11.5 Retry

One retry is allowed only for idempotent setpoint/range commands when:

- the acknowledgement window expired;
- the thermostat is still available;
- observed controlled fields still equal the original precondition;
- no external context or controlled-value change occurred;
- the schedule/override/protection cause remains current;
- limits/capabilities still validate;
- no pause/suspension/fallback exists; and
- command timing permits the retry.

No automatic retry occurs for a Manual Control command, mode reversal, fan restore, partial multi-action plan, action exception with unknown outcome, or changed precondition. A user may issue a new Manual Control command only after the prior result is resolved and the manual minimum interval has elapsed.

## 11.6 Failure states

- **Rejected before call:** record suppression; no Repair unless configuration/actionable policy is invalid.
- **Action call raised before dispatch is known:** command uncertain; no retry; enter Safe Fallback.
- **Action call completed, no acknowledgement:** one eligible retry; otherwise terminal failure.
- **Conflicting state arrived:** external override; no retry.
- **Partial multi-action:** command uncertain and Emergency Pause for affected authority.
- **Three terminal failures/60 minutes:** persistent command lockout Repair.
- **Late acknowledgement after failure:** record recovery but require reconciliation; do not auto-resume an administrator lockout.

# 12. Window and door handling

## 12.1 Binding model

```text
ContactBinding
  binding_id: UUID
  entity_id: binary_sensor
  kind: WINDOW | EXTERIOR_DOOR
  scope: ZONE | EQUIPMENT_GROUP
  open_debounce_seconds
  grace_seconds
  minimum_open_seconds
  close_debounce_seconds
  resume_delay_seconds
  unavailable_policy: TREAT_OPEN | IGNORE_AND_DEGRADE
  notification_after_seconds
  reminder_interval_seconds | None
```

Recommended defaults:

- Window: 30-second open debounce, 120-second grace, 120-second minimum open, 30-second close debounce, 300-second resume.
- Exterior door: 15-second open debounce, 300-second grace/minimum open, 15-second close debounce, 180-second resume.
- Unavailable policy: treat as open for active-control safety.
- Left-open notification: 15 minutes; reminder: 60 minutes.

## 12.2 State machine

`CLOSED → OPEN_DEBOUNCE → GRACE → SUSPENDED → CLOSE_DEBOUNCE → RESUME_DELAY → CLOSED`

- Reclosing before the qualifying deadline cancels suspension.
- Reopening during resume returns to suspended without a command.
- Suspension never sends HVAC Off; it stops Intelligent Climate comfort commands and leaves the thermostat usable.
- An existing thermostat call may continue under native thermostat control.
- In a shared command-authority group, a configured group-scope contact or any zone policy marked “suspend shared group” suppresses all group commands.
- Optional emergency temperature protection may act despite suspension.
- Activity records exact state transitions, not every contact report.

# 13. Occupancy modes

## 13.1 Model

```text
OccupancyPolicy
  sources: tuple[OccupancySourceBinding, ...]
  modes: tuple[OccupancyModeDefinition, ...]
  priority_order
  arrival_delay_seconds
  departure_delay_seconds
  unavailable_fallback: HOME | LAST_CONFIRMED

OccupancyModeDefinition
  mode_id
  name
  built_in_kind | CUSTOM
  zone_effects: map[ZoneId, OccupancyEffect]

OccupancyEffect
  kind: NONE | SELECT_PROFILE | TARGET_OFFSET
  profile_id | None
  heat_offset_c | None
  cool_offset_c | None
```

Defaults: two-minute arrival, ten-minute departure, Home fallback. Vacation may be selected manually and outranks sensor-derived modes until canceled.

## 13.2 Resolution

- Explicit administrator/user-selected Vacation/Guest/Sleep mode outranks automatic sources for its configured duration.
- Automatic sources map raw states to configured modes.
- Priority resolves simultaneous accepted modes.
- Arrival/departure timers use monotonic time at runtime and UTC deadlines for restart persistence.
- Unavailable sources cannot independently force Away.
- A profile/offset change creates a material occupancy transition and may expire an override using that policy.
- Offsets are validated against absolute limits and cannot turn a single target into an unsupported range.
- The decision explanation includes the winning source category and delay; raw person/device names are excluded from diagnostics.

# 14. Entities, actions, events, activity, diagnostics, and Repairs

## 14.1 Entity matrix

Existing Phase 1 entities remain unless explicitly evolved.

### Equipment-group device

| Platform | Entity | Default | Purpose |
|---|---|---:|---|
| Sensor | Equipment relationship | Enabled | Existing |
| Sensor | Thermostat capability status | Enabled | Existing |
| Sensor | Control stage | Enabled | Observe/Manual/Shadow/Scheduled/Fallback/Pause |
| Sensor | Observation status | Enabled | Collection active, usable-source count, and Phase 2 history boundary |
| Sensor | Shadow readiness | Enabled | Qualifying percentage and blocking reason |
| Binary sensor | Configuration degraded | Enabled | Existing |
| Binary sensor | Reconciling | Enabled | Existing |
| Binary sensor | Command fault | Enabled | Uncertain/failed/lockout |
| Binary sensor | Shared conflict | Enabled when applicable | Group arbitration hold |
| Switch | Intelligent automation enabled | Enabled | Master autonomous intent; turning off enters Manual Control by default and never sends a thermostat command |
| Button | Emergency pause | Enabled | Immediate command suppression |
| Event | Activity | Enabled | Existing group material activity |

### Zone device

| Platform | Entity | Default | Purpose |
|---|---|---:|---|
| Climate | Zone climate | Enabled | Read-only in Observe/Shadow; explicit user control in Manual Control; safe override control in Scheduled Control |
| Sensor | Effective temperature | Enabled | Existing |
| Sensor | Effective humidity | Conditional | Existing |
| Sensor | Temperature spread | Conditional diagnostic | Existing |
| Sensor | Valid temperature sources | Diagnostic | Existing |
| Sensor | Operating mode | Enabled | Existing, expanded values |
| Sensor | Scheduled target | Enabled | Base target |
| Sensor | Active target | Enabled | After occupancy/override/protection |
| Sensor | Current schedule period | Enabled | Profile/period label |
| Sensor | Next schedule transition | Enabled | Timestamp |
| Sensor | Override expiration | Conditional | Timestamp or translated policy |
| Sensor | Latest decision | Enabled | Concise reason |
| Sensor | Latest activity | Enabled | Existing |
| Binary sensor | Sensor data degraded | Enabled | Existing |
| Binary sensor | Thermostat data degraded | Enabled | Existing |
| Binary sensor | Manual override active | Enabled | Override status |
| Binary sensor | Window suspension active | Conditional | Contact status |
| Binary sensor | Occupied | Conditional | Resolved Home/occupied semantics |
| Binary sensor | Safe fallback active | Enabled | Command suppression |
| Binary sensor | Fan humidity lockout | Conditional | Fan start blocked |
| Button | Cancel override | Conditional | Ends override through state machine |
| Event | Activity | Enabled | Existing zone material activity |

No per-period entities, per-command entities, raw source entities, model placeholders, or high-frequency timers are created.

## 14.2 Actions

Actions are registered once in `async_setup`; missing/unloaded entries raise translated `ServiceValidationError`, and runtime failures raise translated `HomeAssistantError`.

Each action requires explicit entry/zone targets and typed fields. `set_operating_mode` distinguishes Observe Only, Manual Control, Scheduled Shadow, and the separately guarded Scheduled Control arming workflow. The three `set_manual_*` actions are valid only in Manual Control, require current user context and observed-state revision, and cannot be invoked by an autonomous coordinator callback. `set_temporary_override` accepts safe target/range, optional mode when supported, expiration policy, and policy-specific value. `force_schedule_period` creates an override referencing a canonical period; it does not mutate the weekly schedule.

## 14.3 Events

Existing `intelligent_climate_activity` remains privacy-bounded. Add one typed event, `intelligent_climate_control_event`, with:

- entry/group/optional zone UUID;
- event type;
- reason code;
- timestamp;
- decision/command/override UUID where applicable; and
- concise explanation.

Manual Control records `manual_command_requested`, `manual_command_rejected`, `manual_command_acknowledged`, and `manual_command_failed` as material events. Equivalent observation updates remain deduplicated and do not flood the activity log.

Event types:

- `override_started`
- `override_updated`
- `override_ended`
- `schedule_transition`
- `window_suspension_started`
- `window_suspension_ended`
- `occupancy_mode_changed`
- `safe_fallback_activated`
- `safe_fallback_cleared`
- `shadow_ready`
- `control_armed`
- `control_paused`
- `command_issued`
- `command_acknowledged`
- `command_failed`
- `shared_conflict_started`
- `shared_conflict_ended`
- `fan_lockout_started`
- `fan_lockout_ended`

Command payloads, entity IDs, target temperatures, raw contexts, and exception text are not included in public event data.

## 14.4 Activity

Activity types/reasons expand while retaining schema-strict compatibility. Materiality excludes countdown ticks, unchanged schedule reevaluation, duplicate suppression, equivalent state reports, preview operations, and shadow percentage-only changes below a meaningful threshold.

The sidebar Activity route may request paginated bounded history. Default retention remains 500 records/30 days unless the user changes existing bounds; command journal uses an independent maximum of 100 entries/14 days.

The Today timeline references material activity records by stable typed identifiers; it does not duplicate full activity payloads into every sample. Presentation-trace sampling is not activity and cannot create a public Home Assistant event by itself.

## 14.5 Diagnostics

Diagnostics schema increments to 2 and adds allowlisted:

- operating intent/control state and stable reasons;
- schedule schema/revision/time zone, counts, selected profile IDs, validation status, and transition timestamps;
- targets only if policy permits; default diagnostic projection uses rounded bounded values and never raw source values;
- override policy/state/timestamps/source category, not user/context identifiers;
- contact/occupancy/fan state summaries;
- shadow qualification metrics;
- command counts/status/reason/timing without entity IDs, service payloads, contexts, or exception text;
- presentation-trace schema, retention, first/last timestamp, sample/annotation counts, last successful persistence, and degraded status without raw samples;
- current narrative template/version and included fact categories without rendering user-specific narrative text;
- safety-limit and timing policies;
- migration and frontend/backend schema versions.

## 14.6 Repairs

Add:

- `schedule_invalid`
- `schedule_store_failed`
- `time_zone_acknowledgement_required`
- `active_control_not_qualified`
- `command_failed`
- `command_outcome_uncertain`
- `command_lockout`
- `shared_control_authority_invalid`
- `required_control_entity_missing`
- `frontend_version_mismatch`

Qualification by itself is normal status; a Repair appears only if the user tries to arm active control while a persistent actionable blocker exists.

# 15. Storage migration and startup/reload reconciliation

## 15.1 Versions

| Document | Phase 1 | Phase 2 |
|---|---:|---:|
| Config entry | 1.1 | 2.0 |
| Zone data | 1 | 2 |
| Runtime Store envelope | 1.2 | 2.0 |
| Runtime inner schema | 1 | 2 |
| Schedule Store | Absent | 1.0 / inner 1 |
| Presentation Trace Store | Absent | 1.0 / inner 2 |
| Diagnostics schema | 1 | 2 |
| Frontend API | Absent | 1 |

A major config version is justified because the configuration gains physical command authority and new safety semantics.

## 15.2 Config migration

1. Decode the complete Phase 1 parent/options/zone graph without mutation.
2. Add Phase 2 defaults with `automation_enabled=false`, `desired_operating_mode=observe_only`, observation collection preserved from the accepted Phase 1 setting, default safety/timing values, no command-authority change for single/independent groups, and Phase 1 primary thermostat as the proposed authority for shared groups.
3. Add typed contact, occupancy, and fan bindings only from already configured entity IDs; default each behavior disabled until reviewed.
4. Validate the complete Phase 2 graph.
5. Apply one config-entry update and zone-subentry updates only after every migrated document validates.
6. If a shared group cannot select one unambiguous primary authority, migrate safely to Observe Only and create a Repair; never guess.

## 15.3 Schedule Store creation

Migration creates no enabled control schedule silently. On first Phase 2 setup:

- Schedule Store may be absent.
- UI offers a reviewable starter schedule generated in memory.
- Nothing is saved until the user confirms.
- Saved schedules begin disabled and require shadow activation.

## 15.4 Runtime Store migration

Preserve:

- valid bounded activity records;
- valid comparison-only source baselines;
- group/zone identities;
- clean-shutdown metadata.

Transform:

- Phase 1 `last_runtime_state` to Observe Only/Reconciliation-safe Phase 2 state.
- Always-empty Phase 1 `command_journal` to typed empty v2 journal.
- Add empty overrides, transition ledger, occupancy/contact timers, fan budget, shadow qualification, failure counters, and control intent.
- Add no persisted executable Manual Control command. A stored Manual Control mode is only post-reconciliation user intent; every actual command still requires a new current user action.

Persisted Phase 1 zone temperatures remain nonauthoritative and are not hydrated publicly.

## 15.5 Presentation Trace Store

The auxiliary Store key is `intelligent_climate.presentation.<entry_id>`, with Home Assistant Store envelope 1.0 and `presentation_schema_version: 2`. Schema 2 adds privacy-safe aggregate contact state and material control context; schema 1 traces migrate in memory with those values marked not configured/not reported. It is deliberately outside Runtime Store v2 so invalid or lost visualization history cannot quarantine overrides, command journal, transition ledger, qualification, timers, failure counters, or control intent.

The trace starts empty after Phase 2 migration and is created only after authoritative config/Schedule/Runtime migration succeeds and live reconciliation begins. It may collect only new validated Phase 2 snapshots; it must not convert persisted Phase 1 comparison baselines into chart measurements. Decode failure quarantines/discards only the auxiliary trace and starts a new empty trace. Retention or write failure degrades only the chart/history surface and cannot block ordinary observation or alter control, qualification, activity, or later model learning. Diagnostics and the existing Store Repair report the degraded presentation history honestly.

## 15.6 Multi-document migration safety

Home Assistant cannot atomically update config entries and multiple Stores as one transaction. The safe protocol is:

1. Mark migration in progress in memory; no active adapter exists.
2. Validate proposed config, schedule, and runtime documents.
3. Update config entry to 2.0 with control disabled.
4. Write Schedule Store if a user-confirmed document exists.
5. Write Runtime Store v2.
6. Re-read and validate written Stores.
7. Start Observe Only reconciliation.
8. Only after authoritative migration succeeds, load/create the auxiliary Presentation Trace Store; its failure cannot roll back or alter control state.

Any partial failure leaves control disabled, preserves the original/quarantined payload according to existing policy, and creates a Repair.

## 15.7 Startup/reload sequence

1. Decode/migrate all documents with no adapter.
2. Build configuration and entity indexes.
3. Load schedule and runtime state; reject future/invalid data.
4. Register observation subscriptions, frontend API, and deadlines.
5. Publish Reconciliation snapshot.
6. Require current live thermostat and source states; restored values remain invalid.
7. Reconcile pending journal entries against thermostat state.
8. Detect startup mismatch as external override unless proven acknowledged.
9. Recalculate schedule/occupancy/contact/fan state in shadow.
10. Wait at least 120 seconds, two healthy evaluations at least 30 seconds apart, and all required integrations/entities.
11. If the prior desired mode was Scheduled Control and shadow qualification remains valid, return only after the quiet period; otherwise remain Shadow/Observe. A prior Manual Control intent may return to `MANUAL_IDLE` after the same reconciliation without issuing or reasserting any command.
12. Suppress semantically duplicate commands. Release at most one eligible plan per thermostat, and only from a new current evaluation.

# 16. Shared-equipment conflict resolution

## 16.1 Phase 2 supported topology

- **Single system:** one command-authority thermostat.
- **Independent:** each thermostat is authority only for its assigned zones; no cross-system arbitration.
- **Shared/zoned:** exactly one primary command-authority thermostat. Secondary related thermostats are observed and may create override/conflict suspension but are not commanded in Phase 2.

If active control would require coordinated writes to more than one physical authority in a shared group, the group remains Shadow/Observe until Phase 5.

## 16.2 Demand model

Each eligible zone produces `HEAT`, `COOL`, `SATISFIED`, or `SUPPRESSED`, plus deviation and priority. The group resolver:

1. Removes overridden, window-suspended, invalid, and satisfied demand.
2. Applies emergency protection first.
3. If all remaining demand is one direction, selects the highest-priority zone target for the authority.
4. If heat and cool conflict while equipment is idle, selects the highest-priority eligible zone only when all related thermostat observations are neutral/compatible.
5. If related thermostat state opposes the selected direction, or origin is uncertain, enters `SHARED_CONFLICT_HOLD` and issues no command.
6. If equipment is already active, never reverses direction until the mode-reversal cooldown and current call are safely satisfied; conflicting demand waits.

Priority is the existing configured `zone_priority_order`. Equal/missing priorities are invalid for active shared control.

## 16.3 Deferred Phase 5 behavior

- Multiple command-authority thermostats.
- Anti-starvation rotation and demand accumulation.
- Damper position/control.
- Stage/auxiliary/balance-point logic.
- Equipment-capacity optimization.
- Coordinated transactional target changes across controllers.

# 17. Basic fan control and humidity/dew-point lockouts

## 17.1 Supported controls

- A configured `fan` entity using `fan.turn_on/off`.
- A thermostat’s explicitly advertised fan mode using `climate.set_fan_mode`.

No guessed fan mode names are used. The UI requires the user to map supported modes for circulation and automatic/native operation.

## 17.2 Policy

```text
FanPolicy
  enabled
  control_binding
  strategy: SCHEDULE | TEMPERATURE_SPREAD | EITHER
  spread_start_c
  spread_stop_c
  occupied_only
  allowed_occupancy_modes
  allowed_hvac_modes
  quiet_periods
  minimum_on_seconds
  maximum_runtime_per_hour_seconds
  post_cooling_lockout_seconds
  max_humidity_pct | None
  max_dew_point_c | None
  humidity_unavailable_policy: LOCK_OUT | IGNORE_AND_DEGRADE
```

Recommended defaults: start at 1.1°C/2°F spread, stop at 0.6°C/1°F, minimum on 10 minutes, maximum 20 minutes/hour, 15-minute post-cooling lockout when humidity is elevated, 60% RH limit, 15.6°C/60°F dew-point limit, and lock out when required humidity data is unavailable.

## 17.3 Dew point

Dew point is calculated from effective temperature and relative humidity with a documented Magnus approximation. It is labeled **calculated**, not measured. Invalid/nonfinite temperature or humidity yields no dew point and triggers the configured unavailable policy.

## 17.4 Fan state safety

- Fan start must pass occupancy/time/runtime/humidity/dew-point/post-cooling gates.
- If humidity rises above the lockout threshold while circulation is running, stop at the minimum-on boundary unless immediate stop is configured.
- Prior thermostat fan mode is restored only if the current mode still matches the exact correlated Intelligent Climate circulation command. Any external change cancels restore.
- Failure to stop a separate fan raises a command fault; no repeated rapid off commands occur.
- Fan control is secondary and can never cause a thermostat target/mode command.

# 18. Failure and fallback matrix

| Failure/condition | Detection | Runtime response | Physical command behavior | User surface/recovery |
|---|---|---|---|---|
| Invalid config migration | Strict full-graph decode | Setup blocked or Observe Only | None | Persistent Repair; correct config/reload |
| Invalid/missing Schedule Store | Decode/load failure | Observe Only; retain safe last in-memory schedule only during current runtime | None | Repair; re-save/recover schedule |
| Future Store version | Envelope/version check | Read-only preservation | None | Repair; upgrade integration |
| Time-zone changed | HA config event/start comparison | Shadow/Reconciliation | None | Acknowledge/review schedule |
| Schedule empty/invalid | Validation/evaluation | Zone Safe Fallback | None | Inline UI error; Repair if persisted |
| User disables all automation | Explicit mode change | Manual Control by default, or Observe Only if selected; observation/UI continue | No command on transition; later explicit manual commands only in Manual Control | Banner explains inactive automatic features |
| Observe Only selected | Explicit mode change, migration, or fallback | Continue trusted observation and visible status/history | None under every event | User may remain indefinitely or later select Manual/Shadow |
| Phase 3 model store absent | Phase boundary/version check | Phase 2 observation and Recorder-compatible history continue; no thermal-property claims | No effect | UI states that dedicated learning begins in Phase 3 |
| Required temperature sources below minimum | Phase 1 quality pipeline | Degraded/Safe Fallback | None | Entity/activity; two-evaluation recovery |
| Humidity unavailable | Fan policy | Temperature scheduling continues; fan lockout | No fan start | Warning chip; recover automatically |
| Weather unavailable | Weather observation | Display degraded only | Scheduling continues | UI status; no Repair by default |
| Thermostat unavailable | State/capability | Safe Fallback | None | Repair after startup grace; auto-clear |
| Thermostat capability changed | Capability resolver | Revalidate schedule/control | None until valid | Activity/Repair; edit schedule |
| External thermostat change | Correlation | Manual Override | No schedule correction | Visible expiry/cancel |
| Ambiguous origin and strict override disabled | Correlation | Command uncertainty | None | User resolves; no guess |
| Schedule boundary during override | Timer | Record would-be target | None | Override continues/ends per policy |
| Window opens | Contact state machine | Zone/group suspension | No comfort command; no forced Off | Notification/activity; resume delay |
| Contact unavailable | Policy | Default treat open | None | Degraded indicator; restore automatically |
| Occupancy unavailable | Resolver | Home/last-confirmed fallback | Safe schedule continues | Status/activity |
| Opposite shared demand | Arbitration | Conflict hold | None | Shared-conflict sensor/activity |
| Active shared secondary thermostat conflicts | Observation | Conflict hold/manual override | None | User resolves physical state |
| Command suppressed by deadband/interval | Safety gate | Remain current state; schedule reevaluation | None | Decision reason; not an error |
| Action call exception/unknown dispatch | Adapter | Command uncertain/Safe Fallback | No retry | Repair; administrator acknowledgement |
| No acknowledgement | Deadline | One eligible retry then failure cooldown | At most one retry | Activity/Repair after terminal failure |
| Conflicting state during ack | Correlation | External override | No retry | Override UI |
| Partial multi-action | Tracker | Emergency Pause | No rollback/retry | Persistent Repair |
| Repeated failures | Rolling counter | Command lockout | None | Persistent Repair; explicit clear |
| Home Assistant restart | Lifecycle | Reconciliation/quiet period | None during startup | Status; mismatch becomes override |
| Integration unload/crash | Lifecycle | Runtime absent | No cleanup command | Physical thermostat continues independently |
| Frontend absent/version mismatch | API handshake | Backend control remains safe; admin editing blocked | Existing validated schedule may continue | Repair/banner; update frontend |
| Activity Store write failure | Existing bounded retry | In-memory operation continues | Does not alter command decision | Existing Store Repair |
| Presentation trace invalid/write failed | Discard/quarantine invalid trace; bounded retry | Live values and control continue; built-in historical chart degrades to available data | Does not alter command, qualification, or learning | Timeline warning and existing Store Repair/diagnostic status |
| Schedule Store write failure | Atomic write verification | Old schedule remains authoritative; draft rejected | No effect from draft | Repair/toast; retry save |
| Protection threshold with invalid sensor | Quality gate | No IC protection command | None | Physical thermostat fallback; critical warning |
| User requests unsafe override | Action validation | Reject | None | Translated field error |
| User requests unsafe/stale Manual Control command | Action validation/revision check | Remain Manual Control | Reject; no clamp without renewed confirmation | Inline translated error and refreshed state |
| External out-of-limit physical change | Observation | Override + command suspension | No counter-command | Critical activity/Repair |

# 19. Testing strategy

## 19.1 Quality gates

- Python 3.14 and Home Assistant 2026.7 fixtures.
- At least 95% line and 95% branch coverage for the integration.
- 100% branches for config, options, reconfigure, schedule validation, command safety, and state-machine transition tables.
- TypeScript strict mode and frontend unit/component/accessibility tests.
- Ruff, mypy, hassfest, HACS, JSON/translation validation, frontend lint/format/build.
- Network disabled for backend tests; no real thermostat/cloud account.
- Deterministic clocks, local time zones, event order, service-call recorder, and fake state acknowledgements.
- Private repository CI and live HAOS acceptance before any public synchronization.

## 19.2 Unit test groups

- Schedule schema encode/decode/migration and every invalid field.
- Weekly circular inheritance, identical-target boundaries, empty days, midnight, Sunday/Monday, leap day.
- DST gap and fold in `America/New_York`, plus a non-hour offset zone and a no-DST zone.
- Every override policy, extension, cancel, restart expiry, same-target skip, and occupancy expiry.
- Correlation with context match/mismatch/missing context, delayed ack, external change, and reordered events.
- Every control state/illegal transition/precedence pair.
- Manual Control accepts fresh explicit user intent only; sensor, schedule, deadline, restart, contact, occupancy, weather, learning, and fan-policy events cannot create or repeat a manual command.
- Safety limit intersection, finite values, ranges, deadband, intervals, cooldowns, protection.
- Contact debounce/grace/minimum/resume/unavailable and group escalation.
- Occupancy mapping/priority/delay/unavailable/manual selection/offset limits.
- Shared compatible demand, opposite demand, current-mode hold, authority invalid, and priority.
- Fan spread hysteresis, runtime rolling hour, quiet period, occupancy, post-cooling, RH/dew point, invalid humidity, restore correlation.
- Presentation-trace five-minute bucketing, material-event points, 48-hour retention, rounding, UTC/DST rendering contract, restart persistence, corruption isolation, and proof that no control/learning module imports it.
- Timeline DTO provenance, missing intervals, series omission, annotation linkage, local-day boundaries, and Phase 2 rejection of predicted/planned indoor series.
- Narrative fact-packet validation and template coverage proving that absent weather/model influences and uncommitted model updates can never appear in text.
- Runtime/Schedule Store bounds, revisions, partial failure, migration, quarantine, presentation trace, and future versions.

## 19.3 Integration tests

- 0.0.8 migration through Observe Only with no command.
- Complete UI flow to create/save schedule, shadow qualify, and arm.
- Observe Only and Manual Control UI flows with all schedules/features disabled while sensors, climate, weather, equipment state, activity, and diagnostics remain visible.
- Today timeline and current-status explanation in Observe Only, Manual Control, Shadow, and Scheduled Control, including restart, missing weather, missing intervals, trace corruption, and context-only forecast labeling.
- Manual Control target/mode/fan commands, stale revision rejection, acknowledgement/failure, restart non-replay, and external-change non-reassertion.
- Observe/Shadow no-command sentinel across every event.
- Active scheduled target command and semantic acknowledgement.
- Startup mismatch becomes override; no catch-up command.
- Restart with pending/acked/failed command journal.
- External thermostat target/mode/fan changes.
- Window, occupancy, schedule, and override deadlines sharing one timer.
- Shared group conflict and independent thermostat isolation.
- Action registration, authorization, translated errors, and unloaded entry behavior.
- Entity inventory/availability/unique IDs and Recorder significant-change behavior.
- WebSocket permissions, schema/version handshake, optimistic revision conflict, subscriptions, and cleanup.
- Diagnostics forbidden-string scan and Repair lifecycle.
- Frontend panel/card loading against mock and live backend schemas.
- Frontend chart tests for measured/configured/forecast provenance, line/marker/legend semantics, keyboard access, screen-reader table/summary, DST days, unit conversion, missing-series behavior, compact-card sparkline, and rejection of unsupported future-series kinds.

## 19.4 Mandatory physical-command safety suite

Release blockers:

1. Observe Only and Shadow execute zero calls to climate/fan/switch/humidity/ventilation domains across every scenario.
2. Manual Control produces no physical call unless the test supplies a fresh authenticated user intent; every sensor/timer/restart/automation event produces zero manual calls.
3. Active adapter is the only code path with `hass.services.async_call`.
4. Every physical call targets a configured owned entity and an allowlisted action.
5. Every call has a prior persisted pending journal record and passing safety evaluation.
6. No startup/reload/unload path creates a physical call.
7. No unsafe/unsupported/nonfinite/out-of-limit target creates a call.
8. No external change triggers an immediate counter-command.
9. No uncertain, partial, or Manual Control command produces an automatic retry.
10. No schedule/override/window/occupancy/shared/fan event produces more than the documented bounded calls.
11. Mutation tests fail if the safety gate, shadow sink, manual-intent authority, target ownership, or action allowlist is bypassed.

## 19.5 Manual acceptance

Live HAOS validation includes:

- responsive sidebar at desktop/tablet/phone widths;
- keyboard-only schedule editing;
- card editor and two dashboard cards;
- Observe Only running with complete status visibility and no command path;
- automation-off Manual Control with one safe user-initiated command and proof that schedule/sensor/restart events do not reassert it;
- shadow readiness display and blocked active-control attempt before readiness;
- physical test with a safe, narrow setpoint change;
- wall-thermostat change becoming a visible override;
- restart during override and active schedule;
- open-window suspension;
- activity, Logbook, diagnostics, and Repairs review; and
- integration unload proving the thermostat remains usable.

# 20. Exact Phase 2 acceptance criteria

Every criterion is mandatory. “Pass” requires automated evidence and, where specified, the live HAOS walkthrough.

1. **P2-AC-001:** Release installs as a valid HACS custom integration, passes hassfest/HACS/static quality gates, and retains Home Assistant 2026.7.0 minimum support.
2. **P2-AC-002:** Upgrading an accepted 0.0.8 entry migrates config 1.1/zone 1/runtime Store 1.2 safely to Phase 2 schemas without changing group, zone, source, device, or existing entity unique IDs.
3. **P2-AC-003:** Migration defaults every entry to Observe Only, creates no enabled schedule, constructs no active adapter, and emits zero physical calls.
4. **P2-AC-004:** Missing, invalid, future, corrupt, or partially migrated config/Schedule/Runtime data fails closed, preserves/quarantines data according to policy, and creates the documented Repair.
5. **P2-AC-005:** All normal Phase 2 configuration is possible through Home Assistant UI surfaces without YAML or manual Store editing.
6. **P2-AC-006:** The sidebar panel loads from the integration lifecycle, uses a versioned supported API, cleans up on unload, and never requires a private Home Assistant API.
7. **P2-AC-007:** The panel provides Overview, Schedule, Control, Sensors, Activity, and Settings/Diagnostics, including the Today timeline and current-status explanation, with responsive desktop/tablet/mobile layouts and WCAG AA status/chart semantics.
8. **P2-AC-008:** The zone and schedule cards render in ordinary dashboards, include the Phase 2 configuration editor, and respect read/control permissions.
9. **P2-AC-009:** The core schedule editor supports multiple periods, single/range targets, tolerance, labels, copy day, weekday/weekend templates, enablement, profile selection, preview, save/discard, and inline validation.
10. **P2-AC-010:** Date-specific exceptions, calendar vacation ranges, predictive or psychrometric-comfort fields, simulation runtime, thermal model, and advanced visual editor behavior are absent and cannot influence Phase 2 control; pure policy and injected-sink boundaries remain compatible with a later isolated simulator.
11. **P2-AC-011:** A validated schedule document round-trips deterministically with stable profile/period IDs, canonical ordering, atomic writes, and revision conflict detection.
12. **P2-AC-012:** An invalid schedule write is rejected as a whole and the prior authoritative schedule remains unchanged.
13. **P2-AC-013:** Before-first, after-last, empty-day, midnight, Sunday/Monday, and all-week-empty behavior matches the circular schedule rules.
14. **P2-AC-014:** Spring-forward nonexistent periods execute once at the first valid instant and collapse to at most one final material command plan.
15. **P2-AC-015:** Fall-back ambiguous periods execute on the first occurrence only and cannot duplicate across restart.
16. **P2-AC-016:** A Home Assistant time-zone change suppresses commands, resets shadow qualification, and requires schedule review/acknowledgement.
17. **P2-AC-017:** Scheduled control evaluates correctly without thermal learning, weather, forecast, model confidence, or predictive code.
18. **P2-AC-018:** Observe Only executes zero physical calls across the complete Phase 2 test matrix.
19. **P2-AC-019:** Scheduled Shadow executes zero physical calls while recording the exact validated would-command, suppression reason, and qualification metrics.
20. **P2-AC-020:** Active Scheduled Control cannot be armed before 24 hours, 20 would-command decisions, two material transitions per enabled zone, 95% valid evaluations, and zero blocking fault are satisfied.
21. **P2-AC-021:** Arming active control requires an explicit administrator confirmation naming the command-authority thermostat(s).
22. **P2-AC-022:** Disabled and Emergency Pause suppress every physical action and do not alter the current thermostat/fan state.
23. **P2-AC-023:** Every active physical call passes capability, ownership, mode, limit, range, deadband, interval, cooldown, precondition, correlation, and current-state safety checks immediately before dispatch.
24. **P2-AC-024:** The adapter can invoke only the documented climate/fan actions and only against configured owned entities.
25. **P2-AC-025:** An action-call completion is not treated as success until a matching normalized thermostat/fan state acknowledges it.
26. **P2-AC-026:** An idempotent target/range command retries at most once and only when every retry precondition remains true.
27. **P2-AC-027:** Mode reversal, uncertain dispatch, changed precondition, external change, partial transaction, fan restore, or paused/suspended state never receives a blind retry.
28. **P2-AC-028:** Three terminal failures within 60 minutes create command lockout, Emergency Pause, a persistent Repair, and no further physical call until administrator acknowledgement and reconciliation.
29. **P2-AC-029:** Bad, stale, restored, implausible, jumping, outlier, contradictory, or insufficient sensor data cannot create a thermostat command.
30. **P2-AC-030:** User limits, thermostat advertised limits, finite-value rules, and heat/cool separation prevent every unsafe schedule or UI override command.
31. **P2-AC-031:** A physical/external out-of-limit change becomes a visible external override/control suspension and is not immediately counter-commanded.
32. **P2-AC-032:** A UI-created manual override sends at most one safe initial command and suppresses schedule correction for its controlled fields.
33. **P2-AC-033:** External target, range, mode, preset, fan, or hold changes are classified using command/context/state correlation; ambiguous changes never cause thermostat fighting.
34. **P2-AC-034:** Override source category, start, controlled values, expiration description/time, and cancel/extend controls are visible in the panel and applicable entities.
35. **P2-AC-035:** Every override expiration policy passes deterministic unit, restart, DST, same-target, and integration tests.
36. **P2-AC-036:** Override expiration reevaluates current state and issues at most one eligible command; it never replays a stale suppressed plan.
37. **P2-AC-037:** Window and exterior-door bindings support documented debounce, grace, minimum-open, close debounce, resume, unavailable, scope, and notification policies.
38. **P2-AC-038:** Qualifying contact suspension stops Intelligent Climate comfort commands without sending HVAC Off and resumes only after the configured delay and fresh reevaluation.
39. **P2-AC-039:** Optional emergency temperature protection may override contact/occupancy/schedule/override only when its trustworthy inputs and all hard command gates pass.
40. **P2-AC-040:** Home, Away, Sleep, Vacation, Guest, and custom occupancy modes resolve deterministically with priority, delays, unavailable fallback, and visible source reasoning.
41. **P2-AC-041:** An occupancy mode applies either a selected profile, a bounded target offset, or no target effect per zone; invalid offsets create no command.
42. **P2-AC-042:** Independent thermostat groups remain isolated: one system’s state, failure, override, or cooldown does not command or block another independent authority except entry-wide Emergency Pause.
43. **P2-AC-043:** Shared/zoned active control requires exactly one explicit command authority and a complete unique zone priority order.
44. **P2-AC-044:** Compatible shared demand selects the documented priority result; opposite/uncertain related thermostat demand enters conflict hold and emits no command.
45. **P2-AC-045:** Phase 2 never coordinates physical commands across multiple authorities in a shared group; such a topology remains Shadow/Observe with a clear Repair.
46. **P2-AC-046:** Basic fan control uses only the selected supported fan binding, honors spread hysteresis, occupancy, quiet periods, minimum-on time, hourly runtime, and post-cooling policy.
47. **P2-AC-047:** Humidity or calculated dew point above the configured threshold blocks fan start, and unavailable required humidity follows the configured fail-closed policy.
48. **P2-AC-048:** A thermostat fan mode is restored only when the current state is still correlated to Intelligent Climate; an external fan change cancels restore.
49. **P2-AC-049:** Startup/reload performs no physical call during the 120-second minimum quiet period and required two-evaluation reconciliation.
50. **P2-AC-050:** A startup thermostat/schedule mismatch without conclusive acknowledged-command evidence becomes an external override rather than a catch-up command.
51. **P2-AC-051:** A processed schedule transition cannot execute twice after restart because the persisted transition ledger and semantic dedupe suppress it.
52. **P2-AC-052:** Unload, failed unload, reload, Home Assistant stop, and crash-recovery tests leave the physical thermostat independently usable and create no cleanup command.
53. **P2-AC-053:** The exact Phase 2 entity inventory is stable, uses generated UUID-derived unique IDs, creates no per-period/noisy/future placeholders, and applies appropriate diagnostic/default-disabled categories.
54. **P2-AC-054:** Every action is registered in `async_setup`, validates loaded entry/zone/permissions/inputs, and returns translated validation or runtime errors.
55. **P2-AC-055:** Every documented control event has an exact privacy-bounded schema and is fired once per material transition.
56. **P2-AC-056:** Activity and command histories are chronological, deduplicated, bounded, visible in the panel, and do not grow on equivalent reevaluations.
57. **P2-AC-057:** Diagnostics schema 2 contains the documented allowlist, presentation-trace summary, and narrative-template metadata, and contains no raw trace samples, rendered user-specific narrative, raw entity/user/context/device/account identifiers, service payload, arbitrary attributes, exception text, URL, path, token, or unrounded source data.
58. **P2-AC-058:** Every Phase 2 Repair is created, updated, and cleared according to the documented lifecycle without automatically changing user configuration.
59. **P2-AC-059:** Backend tests achieve at least 95% line and branch coverage and 100% coverage for configuration-flow and safety/state-machine branches; frontend strict/type/unit/component/accessibility gates pass.
60. **P2-AC-060:** Full pytest runs with external sockets disabled and no real climate equipment; all clocks, DST cases, acknowledgements, failures, and state orderings are deterministic.
61. **P2-AC-061:** The mandatory safety suite proves Observe/Shadow no-command behavior, adapter isolation, allowlisted targets/actions, journal-before-call, no unsafe call, no external-change counter-command, and bounded retry.
62. **P2-AC-062:** Live HAOS walkthrough proves the sidebar, Today timeline/current-status explanation, both cards, schedule editing, blocked prequalification arming, qualified shadow, one safe active setpoint command, physical thermostat override, restart, window suspension, activity, diagnostics, Repairs, and unload behavior.
63. **P2-AC-063:** Documentation explains control authority, safety limits, shadow qualification, schedule/DST semantics, overrides, contact/occupancy/fan behavior, Today timeline provenance and phase boundaries, narrative truthfulness, failures, Repairs, privacy, rollback to Observe Only, and continued use of the original thermostat.
64. **P2-AC-064:** With every schedule, occupancy action, contact action, predictive/learned feature, and automatic fan feature disabled, the sidebar, cards, virtual climate status, sensors, thermostat/equipment state, weather, activity, history links, diagnostics, and Repairs remain available and accurately state that automation is off.
65. **P2-AC-065:** Manual Control requires no schedule or shadow qualification, accepts only a fresh explicit user target/mode/fan action, applies capability/ownership/absolute-limit/correlation/acknowledgement/failure gates, and produces zero autonomous or restart-replayed calls and zero automatic retry/reassertion.
66. **P2-AC-066:** Observe Only may run indefinitely, remains fully visible, preserves the bounded presentation trace, Recorder-compatible entity history, and bounded activity, and executes zero physical calls for every sensor, trace sample, timeline/narrative read, timer, restart, reload, external thermostat change, and failure scenario.
67. **P2-AC-067:** Phase 2 labels observation history honestly and exposes no learned thermal property or model-readiness claim; the documented Phase 3 contract can add model-ready observation storage while the user remains in Observe Only or Manual Control without requiring scheduled or predictive control.
68. **P2-AC-068:** In every loaded operating mode, the Overview provides an accessible local-day Today timeline backed by the bounded presentation trace and canonical backend DTO. It correctly distinguishes measured indoor/outdoor values, configured scheduled target, effective target, context-only forecast, actual equipment state, and typed event annotations; handles 23/24/25-hour days and missing intervals; never renders unavailable values as zero; and exposes no Phase 3/4 predicted or planned indoor series.
69. **P2-AC-069:** The Phase 2 current-status explanation is deterministic, local, and derived only from its validated typed fact packet. Tests prove it cannot invent a weather/model cause, predicted result, confidence value, or model adjustment, and that rendering or retrieving the narrative can never create or modify a command, control state, qualification result, schedule, or override.
70. **P2-AC-070:** The private Phase 2 release candidate and all acceptance evidence, including P2-AC-064 through P2-AC-069, pass before any code or release artifact is synchronized to the public repository.

# 21. Dependency-ordered private-first implementation backlog

Every task is implemented and reviewed in the private repository first. Tasks are deliberately small; no task may smuggle in a physical action before its dependency gates.

| Task | Deliverable | Depends on | Physical-control status |
|---:|---|---|---|
| 1 | Freeze 0.0.8 baseline fixtures, acceptance evidence, and Phase 2 forbidden-path sentinels | None | None |
| 2 | Add Phase 2 typed IDs/enums/control reason/execution-context vocabulary, including distinct Observe Only, Manual Control, Manual Override, and Scheduled states, without runtime wiring | 1 | None |
| 3 | Add weekly schedule models, strict JSON codec, and validation tests | 2 | None |
| 4 | Add pure circular schedule evaluator and material-transition calculator | 3 | None |
| 5 | Add DST gap/fold, midnight, week-boundary, and timezone-change tests | 4 | None |
| 6 | Add authoritative Schedule Store v1 with revision, atomic write, quarantine, and tests | 3 | None |
| 7 | Add config 2.0/zone 2/runtime 2 migration models, bounded presentation-trace schema, and dry-run tests | 2, 6 | None |
| 8 | Implement migration transaction, empty presentation-trace initialization, and prove 0.0.8 → Observe Only/no-call behavior | 7 | None |
| 9 | Add pure control precedence and expanded state machine, including manual-intent authority and permanent observation behavior | 2, 4 | None |
| 10 | Add manual override model and all expiration calculators | 4, 9 | None |
| 11 | Add command journal/correlation models with no adapter | 7, 10 | None |
| 12 | Add contact binding/state machine and configuration UI | 9 | None |
| 13 | Add occupancy binding/resolver/effects and configuration UI | 9 | None |
| 14 | Add shared-equipment safety arbitration pure engine | 9, 13 | None |
| 15 | Add fan policy/dew-point/runtime-budget pure engine | 9, 12, 13 | None |
| 16 | Add `SafetyGate`, deadband, interval, cooldown, ownership, and capability tests | 9, 11, 14, 15 | None |
| 17 | Replace Phase 1 intent model with typed `CommandPlan`; add explicit manual versus scheduled authority; retain Observe sink and explicit input/clock/sink dependency boundaries | 16 | Suppressed only |
| 18 | Add Shadow sink, would-command history, qualification metrics, and readiness entities | 17 | Suppressed only |
| 19 | Wire coordinator through schedule/override/contact/occupancy/arbitration/safety into Shadow and populate the nonauthoritative presentation trace | 4, 10, 12–18 | Suppressed only |
| 20 | Add backend WebSocket read/subscribe/observation status/schedule validate/preview/save, Today timeline DTO, deterministic current-narrative fact packet/rendering, and typed manual-control actions | 6, 19 | None |
| 21 | Build frontend API client, theme/accessibility primitives, and schema contract tests | 20 | None |
| 22 | Build sidebar Overview, Sensors, Activity, and Settings shell with complete Observe Only/automation-off visibility, accessible Today timeline, and fact-grounded current-status explanation | 21 | None |
| 23 | Build responsive core schedule editor with revision conflicts and DST preview | 21 | None |
| 24 | Build Control route, Observe/Manual workflows, override workflows, and shadow-readiness confirmation UX | 18, 21 | Suppressed only |
| 25 | Build zone and schedule cards plus minimal card editors, including automation-off status/manual access and optional factual trace sparkline | 21, 23 | Suppressed only |
| 26 | Add Phase 2 entities, actions, events, translations, observation-status truthfulness, and documentation contracts | 19, 24 | Suppressed only |
| 27 | Add diagnostics schema 2 and all Phase 2 Repairs with forbidden-string scans | 19, 26 | Suppressed only |
| 28 | Add active adapter in isolation with fake-service tests, strict action allowlist, and fresh-user-intent sentinel | 16, 17 | Test-only active |
| 29 | Add acknowledgement tracker and one-retry policy against fake thermostat fixtures | 11, 28 | Test-only active |
| 30 | Add separate active-sink construction gates: Manual Control requires reconciled explicit user authority; Scheduled Control additionally requires qualification and arming confirmation | 18, 28, 29 | Gated active |
| 31 | Integrate one single-system Manual Control path and one Scheduled Control setpoint path with all mandatory safety sentinels | 30 | Gated active |
| 32 | Add independent-system active isolation and shared single-authority active path | 14, 31 | Gated active |
| 33 | Add active basic fan path and correlated safe restore | 15, 29, 31 | Gated active |
| 34 | Complete startup/reload/pending-command/mismatch reconciliation and transition ledger | 19, 29–33 | Gated active |
| 35 | Complete failure matrix, authorization, lifecycle, presentation-trace/narrative isolation, performance, and leak tests | 20–34 | Gated active |
| 36 | Complete frontend component/E2E/accessibility/chart-provenance tests and production asset build | 22–25, 35 | No new authority |
| 37 | Run private CI, mutation/safety suite, documentation review, and package candidate | 35, 36 | Release gate |
| 38 | Perform mandatory live HAOS Observe Only and Shadow walkthroughs without active commands | 37 | Observe/Shadow only |
| 39 | Perform controlled live HAOS Manual Control and Scheduled Control command/override/restart/window/unload walkthrough | 38 | Narrow accepted test |
| 40 | Write Phase 2 acceptance record and approve private release candidate | 39 | Release gate |
| 41 | Only after private acceptance, prepare separately reviewed public synchronization | 40 | No automatic publish |

# 22. Known limitations and assumptions

- Phase 2 cannot guarantee compressor minimum-on/off behavior when the thermostat does not expose it; it controls setpoints sparsely and relies on native thermostat protections.
- Home Assistant context propagation varies. Ambiguous changes therefore favor respecting the external state and suppressing commands.
- A shared/zoned system requiring several active thermostat authorities is not eligible for Phase 2 physical control.
- Weather is visible but does not influence scheduled commands.
- Humidity/dew point controls circulation fan eligibility only; no humidity equipment is commanded.
- Psychrometric comfort targeting and comfort-derived effective temperature targets are not part of Phase 2; the literal weekly temperature target remains authoritative.
- The Phase 7 Simulation Lab is not a Phase 2 operating stage. Phase 2 only preserves the pure-policy and injected-sink seams needed to keep that future lab isolated from live control.
- Emergency temperature protection is optional and cannot help when the controlling thermostat or trustworthy indoor temperature is unavailable.
- The integration cannot stop an independent physical user or another automation from choosing a target outside Intelligent Climate limits; it can only refuse to create or counter-command such a value and surface the condition.
- Phase 2’s built-in presentation trace is intentionally limited to 48 hours and is nonauthoritative. Longer public-entity history depends on the user’s Recorder retention/exclusions; Phase 3 creates separate model-ready observation storage, and Phase 7 adds advanced history exploration.
- Phase 2 does not yet create the dedicated long-horizon, model-ready observation dataset or estimate thermal properties. Those begin in Phase 3 and are designed to collect while the entry remains in Observe Only or Manual Control.
- Manual Control is deliberate user operation, not a weak form of scheduled control: it does not apply contact, occupancy, protection, schedule, learning, forecast, or automatic fan policies. The physical thermostat’s native protections and the integration’s ownership/capability/absolute-limit gates still apply.
- Schedule preview around future political time-zone rule changes follows the installed Python time-zone database; a Home Assistant/time-zone update triggers review if semantics change.
- Phase 2 remains pre-alpha active-control software. Observe Only and Shadow are the recommended default until the live acceptance record is complete.

# 23. Approval gates before implementation

The following decisions should be explicitly approved as the Phase 2 product baseline:

1. The Phase 2/Phase 7 schedule editor boundary in PD-01 and PD-17.
2. The mandatory 24-hour/20-decision/two-transition/95% shadow gate in PD-04.
3. The one-command-authority shared-equipment limitation in PD-03.
4. The recommended default limits and timing in §10.
5. The external out-of-limit behavior in PD-08.
6. The administrator/user permission split in PD-16.
7. The isolated Simulation Lab boundary and Phase 7 placement in PD-19.
8. The Phase 4 opt-in psychrometric comfort boundary and Phase 6 humidity-equipment boundary in PD-20.
9. The permanent Observe Only and automation-off Manual Control split in PD-21 and PD-22.
10. The progressive Today/prediction/plan/advanced-visualization boundary and fact-grounded narrative authority rules in PD-23 and PD-24.
11. The separate authoritative Schedule Store, nonauthoritative Presentation Trace Store, and major config/runtime migrations in §15.

No Phase 2 code should begin until these gates and P2-AC-001 through P2-AC-070 are accepted as the implementation contract.

# 24. Evidence and references

Project evidence:

- `Master-specifications.txt`
- `nonnegotiable-requirements.txt`
- `architecture-decisions.txt`
- Redacted Nest diagnostic fixture supplied with the project
- Private repository `GoHoos1/intelligent-climate`, main branch, release 0.0.8
- Private Phase 1 acceptance commit `28dcea6cf9e52361e4c2fd7e3f39a026a3451f03`
- `docs/phase-1-technical-design.md`
- `docs/phase-1-acceptance.md`
- Current 0.0.8 manifest, models, coordinator, storage, entities, diagnostics, Repairs, activity, and command-boundary modules

## Home Assistant implementation references

- Home Assistant custom cards: https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/
- Home Assistant custom panels: https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/
- Extending the Home Assistant WebSocket API: https://developers.home-assistant.io/docs/frontend/extending/websocket-api/
- Integration action registration: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/
- Action error handling: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions/
- Config-flow coverage: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage/
- Integration quality scale: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/

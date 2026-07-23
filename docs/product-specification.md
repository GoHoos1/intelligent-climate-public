# Build an Intelligent Climate Integration for Home Assistant

Act as a senior Home Assistant integration developer, HVAC controls engineer, data engineer, and frontend designer.

Design and implement a production-quality Home Assistant custom integration tentatively named **Intelligent Climate**, using the domain:

`intelligent_climate`

The name and domain should remain easy to change before release.

## Objective

Create a comprehensive, local-first climate-management system for Home Assistant that can coordinate one or more thermostats, temperature sensors, humidity sensors, occupancy sources, weather entities, window and door sensors, circulation fans, HVAC-stage sensors, energy meters, and other climate-related equipment.

The integration should learn how the home responds thermally, predict when heating or cooling should begin, coordinate comfort and efficiency, respect manual thermostat changes, detect possible HVAC problems, and clearly explain every control decision.

The system must be safe, modular, testable, understandable, and useful before its predictive features have collected enough data.

Do not treat this as merely a thermostat scheduler. Treat it as a climate-control platform built around Home Assistant.

## Initial Design Requirement

Before implementing code, produce:

1. A proposed architecture.
2. A repository and file structure.
3. A data model.
4. An entity and device matrix.
5. A zone and equipment relationship model.
6. A control-state machine.
7. A manual-override state machine.
8. A safety and fallback matrix.
9. The proposed thermal-model equations and learning process.
10. A frontend and visual-schedule design.
11. A test strategy.
12. A phased implementation plan.
13. Known limitations and assumptions.

After presenting these items, proceed through the implementation in phases. Do not attempt to place the entire system into one oversized module.

# 1. Home Assistant Architecture

Build this initially as a HACS-installable custom integration, while following current Home Assistant development conventions closely enough that it could potentially be proposed as a core integration later.

All normal setup and configuration must be available through the Home Assistant interface. Do not require YAML configuration.

Implement:

* Config flow.
* Options flow.
* Reconfiguration flow.
* Config-entry versioning and migration.
* Config-entry unloading and reloading.
* Device and entity registry support.
* Stable unique IDs.
* Translations through `strings.json` and translation files.
* Diagnostics with sensitive data redaction.
* Home Assistant Repairs issues when user intervention is required.
* Appropriate entity categories.
* Availability handling.
* Restore-safe state handling.
* Strict typing.
* Asynchronous code without blocking the Home Assistant event loop.
* Automated tests for all important behavior.

Do not use private Home Assistant APIs, monkey-patching, or unsupported frontend techniques.

Determine the latest stable Home Assistant release at implementation time, document the minimum supported release, and use only supported APIs for that release.

# 2. Core Concepts

The system should model the following separately.

## Climate Zone

A climate zone represents a logical area of the home. Each zone may contain:

* One or more thermostats.
* One or more temperature sensors.
* Humidity sensors.
* Window and door sensors.
* Occupancy sensors.
* Supply-air and return-air sensors.
* Circulation fans.
* Air-quality sensors.
* User-defined comfort schedules.
* Its own learned thermal model.

## HVAC Equipment Group

An equipment group represents the physical equipment serving one or more zones.

Examples include:

* A single thermostat controlling a single HVAC system.
* Separate upstairs and downstairs systems.
* Several thermostats controlling shared zoned equipment.
* A thermostat and separate circulation fan.
* Heat-pump equipment with auxiliary heat.
* Dual-fuel equipment.
* Boiler or radiant heating.
* Mini-splits.
* Variable-speed or multistage systems.

The user must be able to specify whether thermostats are independent or share equipment. Shared equipment must have explicit conflict-resolution and zone-priority behavior.

## Operating Modes

At minimum, support:

* Disabled.
* Observe only.
* Scheduled control.
* Predictive control.
* Manual override.
* Away.
* Sleep.
* Vacation.
* Emergency protection.
* Simulation.

The current operating mode and the reason for that mode must be visible to the user.

# 3. Thermostat Control

Allow the user to select one or more existing Home Assistant `climate` entities.

Discover and respect the supported capabilities of each thermostat rather than assuming that every thermostat supports:

* Heating and cooling.
* Auto mode.
* Fan modes.
* Presets.
* Auxiliary heat.
* Multiple stages.
* Humidity control.
* Separate heating and cooling targets.

Never issue commands for features that the underlying thermostat does not expose.

The integration should generally control the existing thermostat through supported Home Assistant climate actions rather than replacing or bypassing the thermostat’s own equipment-safety protections.

Provide a virtual climate entity for each Intelligent Climate zone. This entity should be the main user-facing control surface while the original thermostat entities remain available.

The virtual climate entity should expose only capabilities that can be safely supported by the selected equipment.

# 4. Manual Overrides

A thermostat change not initiated by Intelligent Climate should be treated as an external override when it changes a controlled value such as:

* Target temperature.
* Heating or cooling range.
* HVAC mode.
* Preset.
* Fan mode.
* Hold state.

Maintain a record of the integration’s most recent commands and use command correlation, timing, context, and resulting states to distinguish its own changes from external changes.

Because some thermostat integrations cannot distinguish physical thermostat changes from changes made by another Home Assistant automation, provide an option that determines whether all external changes count as manual overrides.

When an override is detected:

* Stop trying to restore the scheduled target immediately.
* Display the overridden target and override source when known.
* Record when the override started.
* Display when the override will expire.
* Allow the user to cancel or extend it.

Supported override expiration policies should include:

* At the next scheduled setpoint transition.
* After a user-selected duration.
* At the next occupancy-mode transition.
* At a specified clock time.
* Until manually canceled.
* Until the next day’s schedule begins.

The default should be **until the next scheduled setpoint transition**.

Manual changes must never cause the integration and thermostat to fight each other through repeated commands.

# 5. Visual Climate Schedule

Provide a visual weekly schedule for every zone.

The schedule should support:

* Multiple periods per day.
* Separate heating and cooling targets.
* A single target where appropriate.
* Configurable comfort tolerance.
* Copying one day to other days.
* Weekday and weekend templates.
* Sleep periods.
* Home and away periods.
* Temporary schedule exceptions.
* Vacation schedules.
* Date-specific exceptions.
* Schedule enable and disable controls.
* Schedule preview.
* Predicted equipment start time.
* Predicted time-to-target.
* Expected confidence of reaching the target.

The schedule must define what happens before the first period, after the final period, and when a day has no configured periods.

A rich schedule editor will probably require a companion Lovelace card or frontend package. Structure the project so the backend custom integration and frontend schedule card are separate, maintainable components.

The card should include a visual configuration editor so users are not required to edit card YAML manually.

# 6. Adaptive Start and Stop

The system should use learned thermal behavior, current conditions, forecast data, and equipment characteristics to determine when heating or cooling should start.

The objective is to bring the zone within a configurable tolerance of its scheduled target at the scheduled time.

It should calculate and expose:

* Predicted start time.
* Predicted arrival time.
* Estimated time-to-target.
* Expected heating or cooling rate.
* Expected overshoot or undershoot.
* Confidence in the prediction.
* Which inputs most influenced the prediction.
* Whether adaptive start is being used or a fallback schedule is being used.

Support adaptive stopping or coasting when the model predicts that retained heat or cooling will carry the zone to the target without additional runtime.

Predictive control must not be used until the model has enough reliable data. Before that point, use ordinary scheduled control.

If confidence later becomes too low, automatically fall back to safe scheduled operation.

# 7. Thermal Modeling

Begin with an interpretable thermal model rather than an opaque machine-learning system.

A reasonable initial approach would be a first-order or multi-zone resistance-capacitance model that estimates the effects of:

* Indoor temperature.
* Outdoor temperature.
* Heating runtime.
* Cooling runtime.
* HVAC stage when available.
* Solar gain.
* Cloud cover or solar irradiance.
* Wind.
* Indoor and outdoor humidity.
* Circulation fan operation.
* Open windows and doors.
* Occupancy.
* Time of day.
* Adjacent-zone temperatures.
* Equipment cycling.
* Recent thermal history.

Maintain separate learned behavior where useful for:

* Heating.
* Cooling.
* Equipment off.
* Fan-only circulation.
* Different HVAC stages.
* Different seasons or outdoor-temperature ranges.

Expose useful learned values such as:

* Passive heat-loss or heat-gain coefficient.
* Estimated air-exchange influence.
* Solar-gain coefficient.
* Solar phase or peak lag.
* Heating recovery rate.
* Cooling recovery rate.
* Thermal time constant.
* Estimated balance point for heat pumps.
* Temperature response by equipment stage.
* Model residual error.
* Number of usable observations.
* Date of the most recent model update.
* Model confidence.

Confidence should be calculated from more than sample count. It should consider:

* Quantity of usable data.
* Recency.
* Coverage of operating conditions.
* Sensor availability.
* Sensor consistency.
* Residual prediction error.
* Model stability.
* Whether equipment-state data is available.
* Whether the system has observed enough complete heating and cooling cycles.

Provide model states such as:

* Collecting data.
* Initial calibration.
* Usable.
* High confidence.
* Degraded.
* Stale.
* Reset required.

Allow users to reset, export, and inspect model data.

Do not describe calculated efficiency or equipment performance as directly measured unless sufficient energy and equipment-output data exist. Clearly label inferred values as estimates.

# 8. Sensor Handling

Allow the user to select multiple indoor temperature sensors for each zone.

Provide aggregation strategies including:

* Mean.
* Median.
* Minimum.
* Maximum.
* Weighted average.
* Priority sensor.
* Occupied-room preference.
* Warmest-room cooling control.
* Coldest-room heating control.
* Custom per-sensor weights.

Support calibration offsets for individual sensors.

Detect and handle:

* Unavailable sensors.
* Stale sensors.
* Sensors that stop updating.
* Implausible readings.
* Sudden reboot values.
* Large instantaneous jumps.
* Duplicate sensors.
* Sensors reporting in different units.
* Sensors with substantially different update intervals.

A single bad reading must not cause an extreme thermostat command.

Use configurable outlier rejection, minimum-valid-sensor counts, freshness limits, and fallback sensors.

Display which sensors are currently included in the calculated zone temperature and which have been excluded, along with the reason.

# 9. Windows and Doors

Allow window and door contact sensors to be assigned to zones.

Support:

* Open and close debounce.
* A grace period before suspending HVAC.
* Minimum open duration.
* Resume delay after closure.
* Different behavior for windows and exterior doors.
* Per-zone suspension.
* Whole-equipment suspension when zones share equipment.
* Notifications for windows left open.
* Optional reminder intervals.
* Temperature-protection overrides.

For example, ordinary comfort control may pause when a window is open, but freeze protection or dangerous-temperature protection must remain available.

The system should record window-open periods so they can be excluded from or specially classified in thermal-model training.

# 10. Weather and Outdoor Conditions

Allow the user to select one or more Home Assistant weather entities and optional dedicated outdoor sensors.

Use available information such as:

* Current outdoor temperature.
* Forecast temperature.
* Relative humidity.
* Dew point when available or safely calculated.
* Solar irradiance.
* Cloud cover.
* Wind speed.
* Precipitation.
* Forecast uncertainty or forecast age.

Handle missing or unavailable forecast data gracefully.

The integration should continue operating safely if weather data disappears. Predictive confidence should decrease, and the user should be shown that the system is operating with reduced forecast information.

Do not train the thermal model as though forecast values were actual observations. Preserve the distinction between forecast and observed conditions.

# 11. Equipment-Aware Control

During setup, allow the user to identify the equipment type.

Support at minimum:

* Conventional furnace and air conditioner.
* Air-source heat pump.
* Heat pump with auxiliary electric heat.
* Dual-fuel heat pump.
* Boiler.
* Radiant heating.
* Mini-split.
* Multistage equipment.
* Variable-capacity equipment.
* Fan-coil system.
* User-defined or unknown equipment.

For heat pumps, provide configurable controls for:

* Auxiliary-heat avoidance.
* Outdoor auxiliary lockout temperature.
* Outdoor auxiliary allow temperature.
* Maximum acceptable recovery time before auxiliary heat is allowed.
* Maximum setback size.
* Gradual recovery.
* Comfort versus auxiliary-heat savings preference.
* Dual-fuel balance point.
* Emergency heat behavior.
* Maximum continuous runtime before alerting.

Do not assume auxiliary-heat status is exposed by the thermostat. Allow optional external sensors representing:

* Compressor call.
* First-stage heat.
* Second-stage heat.
* Auxiliary heat.
* Emergency heat.
* Cooling stages.
* Blower operation.
* Equipment power use.

If stage data is unavailable, make that limitation clear and avoid claiming that auxiliary heat was detected.

Respect minimum on-times, minimum off-times, deadbands, and maximum command rates. These protections should supplement rather than attempt to defeat the thermostat’s native safeguards.

# 12. Humidity and Circulation Fan Control

Allow one or more humidity sensors to be assigned to each zone.

Support humidity aggregation and stale-sensor handling similar to temperature sensors.

Fan circulation should be able to respond to:

* Temperature spread between rooms.
* Maximum room deviation.
* Occupancy.
* Time of day.
* Heating versus cooling season.
* Indoor humidity.
* Indoor dew point.
* Recent cooling operation.
* User-defined quiet periods.
* Minimum fan-on time.
* Maximum fan runtime per hour.

Provide a configurable maximum humidity or dew-point condition above which circulation is disabled.

Account for the possibility that running the blower after cooling may return retained moisture to the home. Allow circulation after cooling to be restricted or disabled when humidity is elevated.

Permit configurations such as enabling circulation only during the heating season.

Where supported, allow optional coordination with:

* Humidifiers.
* Dehumidifiers.
* Whole-house ventilation.
* ERV or HRV equipment.
* Exhaust fans.

# 13. Occupancy and Home/Away Behavior

Allow occupancy to be determined from one or more Home Assistant entities, including:

* Person entities.
* Device trackers.
* Presence sensors.
* Alarm-panel state.
* Input helpers.
* Bed occupancy.
* Room occupancy.
* User-selected binary sensors.

Support:

* Home.
* Away.
* Sleep.
* Vacation.
* Guest.
* Custom occupancy modes.

Provide arrival and departure delays to avoid rapid changes.

Allow the user to choose whether occupancy changes:

* Select a different schedule.
* Apply a setpoint offset.
* Suspend predictive recovery.
* Trigger preconditioning before expected arrival.
* Affect only selected zones.

Explain which occupancy source caused a mode change.

# 14. Safety and Failure Handling

Safety takes priority over optimization.

Implement configurable absolute heating and cooling limits that no schedule, model, or override may exceed.

Provide emergency protection for:

* Freeze risk.
* Excessive indoor heat.
* Excessive humidity.
* Sensor failure.
* Thermostat unavailability.
* Conflicting thermostat states.
* Repeated command failures.
* Integration restart.
* Home Assistant restart.

When the integration starts or reloads:

* Restore persisted state safely.
* Reconcile the current thermostat state.
* Do not immediately issue a burst of commands.
* Determine whether an external override is already active.
* Validate sensor freshness.
* Validate the current schedule.
* Fall back to conservative scheduled control when model state is uncertain.

If the integration becomes unavailable, it should leave the physical thermostat in a safe, usable state. Avoid designs in which loss of Home Assistant leaves HVAC equipment dependent on continuous integration commands.

Provide a master enable switch and an emergency pause action.

# 15. Shadow and Simulation Modes

Implement two separate testing modes.

## Shadow Mode

Shadow mode uses real thermostat, sensor, weather, and occupancy data but does not send control commands.

It should show:

* The command it would have sent.
* The predicted start time.
* The expected target.
* The reason for the decision.
* Expected auxiliary-heat use.
* Predicted energy or runtime impact where possible.
* Differences between predicted and actual outcomes.

Shadow mode should allow the model and decision engine to be validated before active control is enabled.

## Simulation Mode

Simulation mode must operate without real HVAC equipment.

Provide simulated:

* Climate entities.
* Temperature sensors.
* Humidity sensors.
* Window sensors.
* Occupancy sensors.
* Fan controls.
* Equipment stages.
* Weather conditions.
* Energy use.

The simulation should allow configurable building parameters, including:

* Initial temperature.
* Outdoor temperature profile.
* Heat-loss rate.
* Solar gain.
* Heating capacity.
* Cooling capacity.
* Humidity behavior.
* Sensor noise.
* Sensor failures.
* Window-opening events.
* Occupancy heat gain.
* Equipment faults.

Support deterministic scenarios so automated tests can reproduce the same results.

Include fault injection and recorded-data replay where practical.

Simulation mode must be clearly identified and must never send commands to real entities.

# 16. Explainability and Decision History

Every control decision should produce a human-readable explanation.

Examples:

* “Heating started 42 minutes early because the zone is predicted to require 39–48 minutes to reach 70°F.”
* “Scheduled control is being used because model confidence is below the predictive-control threshold.”
* “Cooling is paused because the dining-room window has been open for 6 minutes.”
* “The circulation fan was not started because indoor humidity is above the configured limit.”
* “The manual setting of 72°F will remain active until the 10:00 PM schedule transition.”
* “Auxiliary heat avoidance is limiting the recovery rate.”

Maintain a bounded decision history containing:

* Timestamp.
* Zone.
* Previous state.
* New state.
* Trigger.
* Input values.
* Decision.
* Command sent.
* Command result.
* Confidence.
* Human-readable explanation.

Expose the latest decision and next planned action as Home Assistant entities.

Avoid unbounded database growth.

# 17. Diagnostics and Equipment Monitoring

Track useful operational statistics, including:

* Heating runtime.
* Cooling runtime.
* Auxiliary-heat runtime when actually observable.
* Fan runtime.
* Cycle count.
* Average cycle duration.
* Starts per hour.
* Duty cycle.
* Time-to-target.
* Temperature rise or fall rate.
* Overshoot.
* Undershoot.
* Room-to-room temperature spread.
* Supply and return temperature difference when sensors exist.
* Outdoor-temperature-correlated performance.
* Forecast error.
* Model prediction error.
* Manual-override frequency.
* Window-related suspension time.
* Command failures.

Support configurable detection and alerting for:

* Failure to heat.
* Failure to cool.
* Excessive continuous runtime.
* Excessive short cycling.
* Unexpected auxiliary-heat use.
* Unexpected stage operation.
* Low or abnormal supply/return temperature difference.
* Increasing recovery times.
* Excessive temperature overshoot.
* Thermostat unavailable.
* Critical sensor unavailable.
* Stale sensor.
* Contradictory sensors.
* Window left open.
* Dangerous indoor temperature.
* High indoor humidity.
* Possible frozen coil.
* Possible condensate or leak condition when a sensor exists.
* Possible filter restriction.
* Model degradation or drift.
* Forecast source unavailable.
* Repeated rejected or failed commands.

Alerts should have configurable severity, debounce, cooldown, and recovery behavior.

Use Home Assistant events and entities so users can build their own automations. Optionally support persistent notifications and user-selected notification actions.

Configuration problems requiring intervention should use Home Assistant Repairs.

# 18. Entities

Create only useful entities and disable noisy or advanced diagnostic entities by default where appropriate.

Potential entities include:

## Climate

* Intelligent Climate virtual climate entity for each zone.

## Sensors

* Effective zone temperature.
* Effective zone humidity.
* Scheduled target.
* Active target.
* Predicted start time.
* Predicted arrival time.
* Time-to-target.
* Predicted temperature at the next schedule transition.
* Model confidence.
* Model state.
* Heating recovery rate.
* Cooling recovery rate.
* Passive thermal coefficient.
* Solar-gain coefficient.
* Thermal time constant.
* Runtime today.
* Cycle count today.
* Latest decision.
* Next planned action.
* Temperature spread.
* Estimated efficiency, clearly marked as estimated.
* Forecast availability.
* Number of valid temperature sensors.

## Binary Sensors

* Model ready.
* Manual override active.
* Window suspension active.
* Occupied.
* Predictive control active.
* Equipment-performance warning.
* Sensor-data degraded.
* Weather-data degraded.
* Safe fallback active.

## Switches

* Intelligent control enabled.
* Predictive control enabled.
* Shadow mode.
* Simulation mode.
* Adaptive start.
* Adaptive stop.
* Fan circulation.
* Auxiliary-heat avoidance.

## Buttons

* Cancel override.
* Reset thermal model.
* Recalculate model.
* Clear alert.
* Export diagnostics.
* Run simulation scenario.

## Numbers and Selects

Expose user-adjustable settings through the options flow or entities only where entity-based control is genuinely useful.

Avoid creating hundreds of entities for internal implementation details.

# 19. User Interface

Create a polished Lovelace card or dashboard experience that shows:

* Current zone temperature and target.
* Current HVAC action.
* Current operating mode.
* Manual-override status.
* Current schedule period.
* Next schedule transition.
* Predicted equipment start.
* Predicted time-to-target.
* Model confidence.
* Sensor health.
* Window and occupancy status.
* Current weather influence.
* Latest decision explanation.
* Next planned action.
* Runtime and cycle summaries.
* Equipment warnings.

Provide dedicated views for:

1. Zone overview.
2. Visual weekly schedule.
3. Thermal model.
4. Equipment performance.
5. Sensor health.
6. Decision history.
7. Simulation.
8. Alerts and diagnostics.

The design should be responsive, elegant, and understandable to nontechnical users while still providing advanced details when expanded.

# 20. Persistence and Data Management

Use versioned persistent storage for:

* Zone configuration.
* Schedule data.
* Model coefficients.
* Model confidence information.
* Override state.
* Learned equipment behavior.
* Bounded decision history.
* Simulation scenarios.

Handle migrations between storage versions.

Avoid writing state on every sensor update. Batch or debounce persistent writes.

Avoid unnecessary Recorder and database growth by:

* Updating entities only when meaningful values change.
* Rounding derived values appropriately.
* Disabling noisy diagnostic entities by default.
* Keeping high-frequency internal observations out of the Home Assistant state machine where practical.
* Maintaining bounded internal histories.

Provide export and import for schedules, model data, and simulation scenarios.

All modeling and decision-making should run locally unless an optional external provider is explicitly added in the future.

# 21. Actions and Events

Provide documented actions for operations such as:

* Pause control.
* Resume control.
* Set temporary override.
* Cancel override.
* Force a schedule period.
* Reset a zone model.
* Recalculate a model.
* Enable or disable predictive control.
* Run a simulation scenario.
* Export model information.
* Acknowledge an alert.

Fire documented Home Assistant events for:

* Override started.
* Override ended.
* Schedule transition.
* Adaptive start.
* Adaptive stop.
* Window suspension.
* Window suspension ended.
* Model became ready.
* Model became degraded.
* Safe fallback activated.
* Equipment warning detected.
* Equipment warning cleared.
* Command failed.

# 22. Testing

Create automated tests for at least:

* Initial config flow.
* Options flow.
* Reconfiguration.
* Duplicate configuration prevention.
* Config-entry unloading.
* Config-entry migration.
* Entity creation.
* Capability detection.
* Manual override detection.
* Every override expiration policy.
* Schedule transitions.
* Adaptive start.
* Adaptive fallback at low confidence.
* Window debounce and suspension.
* Sensor outlier rejection.
* Stale sensors.
* Sensor values following a reboot.
* Missing weather data.
* Thermostat unavailability.
* Command failure.
* Restart reconciliation.
* Shared-equipment conflicts.
* Heat-pump auxiliary-heat rules.
* Fan humidity lockout.
* Occupancy transitions.
* Shadow mode.
* Simulation mode.
* Thermal-model updates.
* Model reset.
* Diagnostics redaction.
* Repairs issue creation and resolution.
* Persistence and migration.
* Temperature-unit conversion.
* Daylight-saving-time transitions.
* Midnight and week-boundary schedule transitions.

Target greater than 95 percent test coverage, with complete config-flow coverage.

Use deterministic clocks and deterministic simulated data in tests.

# 23. Phased Delivery

Implement the system in manageable phases.

## Phase 1: Foundation and Observation

* Config flow and options flow.
* Zone and equipment configuration.
* Entity selection.
* Virtual climate entity.
* Sensor aggregation.
* Observe-only mode.
* Decision logging.
* Basic diagnostics.
* Safe restart behavior.
* Initial tests.

## Phase 2: Safe Scheduled Control

* Weekly scheduling.
* Manual overrides.
* Window and door handling.
* Occupancy modes.
* Safety limits.
* Basic fan control.
* Schedule UI.
* Full fallback behavior.

## Phase 3: Thermal Learning

* Observation storage.
* Interpretable thermal model.
* Heating, cooling, and passive coefficients.
* Confidence calculation.
* Model diagnostics.
* Shadow predictions.
* Model reset and export.

## Phase 4: Predictive Control

* Adaptive start.
* Adaptive stop.
* Forecast input.
* Time-to-target prediction.
* Confidence-based fallback.
* Overshoot control.
* Decision explanations.

## Phase 5: Equipment Intelligence

* Heat-pump behavior.
* Auxiliary-heat policies.
* Stage inputs.
* Shared-equipment coordination.
* Performance alerts.
* Runtime-derived maintenance indicators.
* Energy and cost inputs.

## Phase 6: Advanced Climate Features

* Humidifiers and dehumidifiers.
* Ventilation and air-quality coordination.
* Advanced circulation.
* Multi-zone thermal coupling.
* Energy-price optimization.
* Solar-production awareness.
* Demand-response support.

## Phase 7: Simulation and Frontend Completion

* Full virtual-home simulator.
* Fault injection.
* Scenario replay.
* Advanced schedule editor.
* Thermal-model visualizations.
* Equipment-performance dashboard.
* Visual card editor.

Each phase must leave the integration in a usable and testable state.

# 24. Acceptance Criteria

The project is not complete unless:

* A user can configure it entirely through the Home Assistant interface.
* It can control multiple independent or related thermostats.
* Manual thermostat changes are respected.
* Override expiration is predictable and visible.
* Bad or stale sensors cannot cause extreme control actions.
* Open windows are handled with configurable protection behavior.
* Scheduled control works before thermal learning is complete.
* Predictive control is used only when confidence is sufficient.
* Every predictive action is explainable.
* Failure of weather data does not stop ordinary climate control.
* Restarting Home Assistant does not cause unsafe commands.
* Loss of the integration leaves the physical thermostat usable.
* Heat-pump auxiliary-heat behavior is configurable.
* Missing HVAC-stage data is handled honestly.
* Fan circulation can be disabled based on humidity or dew point.
* Simulation mode cannot control real equipment.
* Shadow mode clearly shows proposed actions without executing them.
* Model values include confidence and supporting information.
* Estimated values are distinguished from measurements.
* Diagnostics redact sensitive information.
* The implementation includes comprehensive documentation and tests.

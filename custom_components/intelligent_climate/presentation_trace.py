"""Bounded, nonauthoritative presentation trace runtime for Phase 2."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .models.identifiers import EquipmentGroupId, ZoneId
from .models.policy_runtime import Phase2PolicySnapshot
from .models.presentation import (
    PRESENTATION_TRACE_MAX_ANNOTATIONS,
    PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE,
    PRESENTATION_TRACE_RETENTION_HOURS,
    PRESENTATION_TRACE_STORE_MINOR_VERSION,
    PRESENTATION_TRACE_STORE_VERSION,
    PresentationContactState,
    PresentationControlContext,
    PresentationFanAction,
    PresentationHvacAction,
    PresentationPointKind,
    PresentationQualityFlag,
    PresentationTraceDocument,
    PresentationTracePoint,
    decode_presentation_trace_document,
    empty_presentation_trace,
    encode_presentation_trace_document,
    validate_presentation_trace,
)
from .models.runtime import (
    EntryObservationSnapshot,
    NormalizedClimateState,
    ZoneObservation,
)
from .models.schedule import TargetKind, TargetSpec
from .models.schema import SchemaValidationError

_SAVE_DELAY = timedelta(minutes=15)

type NowFunction = Callable[[], datetime]


class _PresentationDataStore(Store[dict[str, Any]]):
    """Home Assistant Store envelope isolated from authoritative runtime data."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        super().__init__(
            hass,
            PRESENTATION_TRACE_STORE_VERSION,
            key,
            atomic_writes=True,
            minor_version=PRESENTATION_TRACE_STORE_MINOR_VERSION,
            max_readable_version=PRESENTATION_TRACE_STORE_VERSION,
        )


class PresentationTraceRuntime:
    """Collect rounded UI history without exposing it to control policy."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        equipment_group_id: EquipmentGroupId,
        zone_ids: tuple[ZoneId, ...],
        contact_entity_ids_by_zone: Mapping[ZoneId, tuple[str, ...]] | None = None,
        now_fn: NowFunction = utcnow,
    ) -> None:
        if not isinstance(equipment_group_id, EquipmentGroupId):
            raise ValueError("equipment_group_id must be typed")
        if not zone_ids or any(not isinstance(item, ZoneId) for item in zone_ids):
            raise ValueError("zone_ids must be a nonempty typed tuple")
        self._hass = hass
        self._entry_id = entry_id
        self._equipment_group_id = equipment_group_id
        self._zone_ids = tuple(zone_ids)
        self._expected_zone_ids = frozenset(self._zone_ids)
        self._contact_entity_ids_by_zone = {
            zone_id: tuple((contact_entity_ids_by_zone or {}).get(zone_id, ()))
            for zone_id in self._zone_ids
        }
        self._now_fn = now_fn
        self._store = _PresentationDataStore(
            hass, f"intelligent_climate.presentation.{entry_id}"
        )
        self._document = empty_presentation_trace(
            entry_id=entry_id,
            equipment_group_id=equipment_group_id,
            zone_ids=self._zone_ids,
            saved_at_utc=self._now(),
        )
        self._loaded = False
        self._degraded = False
        self._dirty = False
        self._cancel_save: CALLBACK_TYPE | None = None
        self._write_task: asyncio.Task[None] | None = None
        self._closing = False

    @property
    def document(self) -> PresentationTraceDocument:
        """Return the current immutable, nonauthoritative trace."""
        return self._document

    @property
    def degraded(self) -> bool:
        """Return whether trace loading or persistence has degraded."""
        return self._degraded

    @property
    def dirty(self) -> bool:
        """Return whether a material trace change awaits persistence."""
        return self._dirty

    async def async_load(self) -> None:
        """Load valid history or start empty without affecting control state."""
        if self._loaded:
            return
        try:
            raw = await self._store.async_load()
            if raw is not None:
                self._document = decode_presentation_trace_document(
                    raw,
                    expected_entry_id=self._entry_id,
                    expected_equipment_group_id=self._equipment_group_id,
                    expected_zone_ids=self._expected_zone_ids,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._degraded = True
            self._document = empty_presentation_trace(
                entry_id=self._entry_id,
                equipment_group_id=self._equipment_group_id,
                zone_ids=self._zone_ids,
                saved_at_utc=self._now(),
            )
        self._loaded = True

    def record_snapshot(
        self,
        observation: EntryObservationSnapshot,
        policy: Phase2PolicySnapshot,
    ) -> bool:
        """Append at most one rounded point per affected zone and schedule save."""
        if not self._loaded:
            raise RuntimeError("presentation trace must be loaded")
        if observation.entry_id != self._entry_id:
            raise ValueError("observation entry does not match trace")
        if policy.observation_revision != observation.revision:
            raise ValueError("policy and observation revisions must match")
        now = _utc(observation.calculated_at)
        cutoff = now - timedelta(hours=PRESENTATION_TRACE_RETENTION_HOURS)
        samples: dict[ZoneId, tuple[PresentationTracePoint, ...]] = {}
        changed = False
        zones = {item.zone_id: item for item in observation.zones}
        for zone_id in self._zone_ids:
            previous = tuple(
                point
                for point in self._document.samples_by_zone.get(zone_id, ())
                if point.timestamp_utc >= cutoff
            )
            zone = zones.get(zone_id)
            policy_zone = policy.zone(zone_id)
            if zone is None or policy_zone is None:
                samples[zone_id] = previous
                continue
            point = _trace_point(
                zone,
                policy_zone,
                previous,
                now,
                contact_state=self._contact_state(zone_id),
            )
            if point is not None:
                previous = (*previous, point)[-PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE:]
                changed = True
            samples[zone_id] = previous
        annotations = tuple(
            item for item in self._document.annotations if item.timestamp_utc >= cutoff
        )[-PRESENTATION_TRACE_MAX_ANNOTATIONS:]
        if changed or any(
            len(samples[zone_id])
            != len(self._document.samples_by_zone.get(zone_id, ()))
            for zone_id in self._zone_ids
        ):
            self._document = PresentationTraceDocument(
                entry_id=self._entry_id,
                equipment_group_id=self._equipment_group_id,
                saved_at_utc=now,
                samples_by_zone=MappingProxyType(samples),
                annotations=annotations,
            )
            validate_presentation_trace(
                self._document, expected_zone_ids=self._expected_zone_ids
            )
            self._dirty = True
            self._schedule_save()
            return True
        return False

    async def async_flush(self) -> None:
        """Persist the current trace once; failure degrades only presentation."""
        if not self._dirty or self._closing:
            return
        self._cancel_scheduled_save()
        encoded = dict(
            encode_presentation_trace_document(
                self._document,
                expected_zone_ids=self._expected_zone_ids,
            )
        )
        try:
            await self._store.async_save(encoded)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._degraded = True
            return
        self._dirty = False

    async def async_shutdown(self) -> None:
        """Perform the orderly-shutdown write and release owned callbacks."""
        if self._closing:
            return
        self._cancel_scheduled_save()
        if self._write_task is not None:
            await self._write_task
        if self._dirty:
            encoded = dict(
                encode_presentation_trace_document(
                    self._document,
                    expected_zone_ids=self._expected_zone_ids,
                )
            )
            try:
                await self._store.async_save(encoded)
                self._dirty = False
            except asyncio.CancelledError:
                raise
            except Exception:
                self._degraded = True
        self._closing = True

    def _schedule_save(self) -> None:
        if self._cancel_save is not None or self._closing:
            return
        self._cancel_save = async_call_later(
            self._hass,
            _SAVE_DELAY.total_seconds(),
            self._async_save_due,
        )

    async def _async_save_due(self, _: datetime) -> None:
        self._cancel_save = None
        if self._closing or not self._dirty:
            return
        self._write_task = self._hass.async_create_task(
            self.async_flush(), "Intelligent Climate presentation trace save"
        )
        try:
            await self._write_task
        finally:
            self._write_task = None

    def _cancel_scheduled_save(self) -> None:
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None

    def _now(self) -> datetime:
        return _utc(self._now_fn())

    def _contact_state(self, zone_id: ZoneId) -> PresentationContactState:
        entity_ids = self._contact_entity_ids_by_zone.get(zone_id, ())
        if not entity_ids:
            return PresentationContactState.NOT_CONFIGURED
        states = tuple(self._hass.states.get(entity_id) for entity_id in entity_ids)
        if any(state is not None and state.state == STATE_ON for state in states):
            return PresentationContactState.OPEN
        if states and all(
            state is not None and state.state == STATE_OFF for state in states
        ):
            return PresentationContactState.CLOSED
        if any(
            state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}
            for state in states
        ):
            return PresentationContactState.UNAVAILABLE
        return PresentationContactState.UNAVAILABLE


def _trace_point(
    zone: ZoneObservation,
    policy: object,
    previous: tuple[PresentationTracePoint, ...],
    now: datetime,
    *,
    contact_state: PresentationContactState,
) -> PresentationTracePoint | None:
    from .models.policy_runtime import ZonePolicySnapshot

    if not isinstance(policy, ZonePolicySnapshot):
        raise ValueError("policy zone must be typed")
    latest = previous[-1] if previous else None
    if latest is not None and now <= latest.timestamp_utc:
        # Presentation history must never invent time to force a material state
        # change into canonical order. A later observation will record it.
        return None
    temperature = _rounded(zone.effective_temperature_c)
    humidity = _rounded(zone.effective_humidity_pct)
    scheduled = _rounded_target(policy.scheduled_target)
    effective = _rounded_target(policy.effective_target)
    thermostat = _primary_thermostat(zone.thermostat_states)
    hvac = _hvac_action(thermostat)
    fan = _fan_only_action(thermostat)
    control_context = _control_context(policy.control_state.value)
    quality = _quality_flags(zone)
    material = latest is None or (
        latest.scheduled_target != scheduled
        or latest.effective_target != effective
        or latest.hvac_action is not hvac
        or latest.fan_action is not fan
        or latest.contact_state is not contact_state
        or latest.control_context is not control_context
        or latest.quality_flags != quality
    )
    bucket = now.replace(
        minute=now.minute - now.minute % 5,
        second=0,
        microsecond=0,
    )
    if not material and latest is not None and latest.timestamp_utc >= bucket:
        return None
    timestamp = now if material else bucket
    kind = (
        PresentationPointKind.MATERIAL_CHANGE
        if material
        else PresentationPointKind.FIVE_MINUTE_BUCKET
    )
    return PresentationTracePoint(
        point_id=uuid4(),
        zone_id=zone.zone_id,
        timestamp_utc=timestamp,
        kind=kind,
        effective_temperature_c=temperature,
        effective_humidity_pct=humidity,
        outdoor_temperature_c=None,
        scheduled_target=scheduled,
        effective_target=effective,
        hvac_action=hvac,
        fan_action=fan,
        quality_flags=quality,
        annotation_ids=(),
        contact_state=contact_state,
        control_context=control_context,
    )


def _control_context(value: str) -> PresentationControlContext:
    return {
        "manual_override": PresentationControlContext.MANUAL_OVERRIDE,
        "window_suspended": PresentationControlContext.WINDOW_SUSPENDED,
        "shared_conflict_hold": PresentationControlContext.SHARED_CONFLICT,
        "safe_fallback": PresentationControlContext.SAFE_FALLBACK,
        "emergency_paused": PresentationControlContext.PAUSED,
        "degraded": PresentationControlContext.DEGRADED,
    }.get(value, PresentationControlContext.NORMAL)


def _quality_flags(zone: ZoneObservation) -> tuple[PresentationQualityFlag, ...]:
    result = [
        (
            PresentationQualityFlag.TEMPERATURE_DEGRADED
            if zone.sensor_data_degraded
            else PresentationQualityFlag.TEMPERATURE_VALID
        ),
        (
            PresentationQualityFlag.THERMOSTAT_DEGRADED
            if zone.thermostat_data_degraded
            else PresentationQualityFlag.THERMOSTAT_VALID
        ),
    ]
    if zone.humidity_aggregation is not None:
        result.append(
            PresentationQualityFlag.HUMIDITY_DEGRADED
            if zone.humidity_aggregation.effective_value is None
            else PresentationQualityFlag.HUMIDITY_VALID
        )
    return tuple(result)


def _primary_thermostat(
    states: tuple[NormalizedClimateState, ...],
) -> NormalizedClimateState | None:
    """Prefer the first available configured thermostat for presentation."""
    return next(
        (state for state in states if state.available),
        states[0] if states else None,
    )


def _hvac_action(
    thermostat: NormalizedClimateState | None,
) -> PresentationHvacAction:
    if thermostat is None:
        return PresentationHvacAction.NOT_REPORTED
    if not thermostat.available:
        return PresentationHvacAction.UNAVAILABLE
    if thermostat.hvac_action is None:
        return PresentationHvacAction.NOT_REPORTED
    raw = getattr(thermostat.hvac_action, "value", thermostat.hvac_action)
    aliases = {"fan_only": PresentationHvacAction.FAN}
    if str(raw) in aliases:
        return aliases[str(raw)]
    try:
        return PresentationHvacAction(str(raw))
    except ValueError:
        return PresentationHvacAction.UNKNOWN


def _fan_only_action(
    thermostat: NormalizedClimateState | None,
) -> PresentationFanAction:
    """Report explicit fan-only circulation, never the HVAC-driven blower."""
    if thermostat is None:
        return PresentationFanAction.NOT_REPORTED
    if not thermostat.available:
        return PresentationFanAction.UNAVAILABLE
    hvac_raw = getattr(thermostat.hvac_action, "value", thermostat.hvac_action)
    if hvac_raw in {"fan", "fan_only"}:
        return PresentationFanAction.ON
    if thermostat.fan_mode is None:
        return PresentationFanAction.NOT_REPORTED
    raw = thermostat.fan_mode.strip().lower()
    if raw in {
        "on",
        "circulate",
        "circulation",
        "fan_only",
        "low",
        "medium",
        "high",
    }:
        return PresentationFanAction.ON
    if raw in {"off", "auto"}:
        return PresentationFanAction.OFF
    return PresentationFanAction.UNKNOWN


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)


def _rounded_target(value: TargetSpec | None) -> TargetSpec | None:
    if value is None:
        return None
    if value.kind is TargetKind.SINGLE:
        return replace(value, target_c=_rounded(value.target_c))
    return replace(
        value,
        heat_target_c=_rounded(value.heat_target_c),
        cool_target_c=_rounded(value.cool_target_c),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchemaValidationError("timestamp", "must be timezone-aware")
    return value.astimezone(UTC)

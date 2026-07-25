"""Test deterministic diagnostics projection helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from custom_components.intelligent_climate.diagnostics import (
    _binding_kind,
    _ReportPseudonymizer,
    _source_group_projection,
)
from custom_components.intelligent_climate.models import (
    AggregationReason,
    AggregationStatus,
    ExclusionReason,
    HumiditySource,
    ObservationSourceId,
    SourceAggregationResult,
    SourceObservation,
    SourceQuality,
    TemperatureSource,
)

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)
SOURCE_IDS = tuple(
    ObservationSourceId.parse(f"00000000-0000-4000-8000-{index:012d}")
    for index in range(1, len(SourceQuality) + 1)
)


def _temperature_source(
    index: int,
    *,
    entity_id: str | None = None,
    attribute: str | None = None,
    enabled: bool = True,
) -> TemperatureSource:
    return TemperatureSource(
        source_id=SOURCE_IDS[index],
        entity_id=entity_id or f"sensor.private_{index}",
        attribute=attribute,
        offset_c=0.25,
        weight=1.5,
        priority=index,
        enabled=enabled,
    )


def _observation(index: int, quality: SourceQuality) -> SourceObservation[float]:
    valid = quality is SourceQuality.VALID
    return SourceObservation(
        source_id=SOURCE_IDS[index],
        raw_value="private raw provider value",
        normalized_value=20.0 if valid else None,
        observed_at=NOW,
        source_last_reported=NOW,
        quality=quality,
        exclusion_reason=None if valid else ExclusionReason(quality.value),
        restored=quality is SourceQuality.RESTORED_NOT_CONFIRMED,
    )


def test_report_pseudonyms_are_typed_bounded_and_cached() -> None:
    """The same typed reference is stable only inside one report scope."""
    pseudonyms = _ReportPseudonymizer(b"a" * 32)

    entity = pseudonyms.entity("sensor.private_temperature")
    same_entity = pseudonyms.entity("sensor.private_temperature")
    other_entity = pseudonyms.entity("sensor.other_temperature")
    name = pseudonyms.name("sensor.private_temperature")

    assert entity == same_entity
    assert entity != other_entity
    assert entity != name
    assert re.fullmatch(r"entity_[0-9a-f]{12}", entity)
    assert re.fullmatch(r"name_[0-9a-f]{12}", name)
    assert "sensor.private_temperature" not in repr(pseudonyms)


def test_report_pseudonyms_change_with_report_salt() -> None:
    """Independent report secrets prevent casual cross-report correlation."""
    first = _ReportPseudonymizer(b"a" * 32)
    second = _ReportPseudonymizer(b"b" * 32)

    assert first.entity("sensor.private") != second.entity("sensor.private")


@pytest.mark.parametrize(
    ("salt", "operation", "message"),
    [
        (b"short", None, "at least 16 bytes"),
        (b"a" * 32, "empty", "must not be empty"),
    ],
)
def test_report_pseudonymizer_rejects_invalid_inputs_without_echoing_values(
    salt: bytes,
    operation: str | None,
    message: str,
) -> None:
    """Pseudonymizer exceptions remain bounded and value-free."""
    if operation is None:
        with pytest.raises(ValueError, match=message):
            _ReportPseudonymizer(salt)
        return

    pseudonyms = _ReportPseudonymizer(salt)
    with pytest.raises(ValueError, match=message):
        pseudonyms.entity("")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (_temperature_source(0), "sensor_state"),
        (
            _temperature_source(0, attribute="current_temperature"),
            "climate_current_temperature",
        ),
        (
            HumiditySource(
                source_id=SOURCE_IDS[0],
                entity_id="climate.private",
                attribute="current_humidity",
                offset_pct=0,
                weight=1,
                priority=0,
                enabled=True,
            ),
            "climate_current_humidity",
        ),
        (
            _temperature_source(0, attribute="private_provider_attribute"),
            "unsupported_attribute",
        ),
    ],
)
def test_binding_kinds_are_bounded(
    source: TemperatureSource | HumiditySource,
    expected: str,
) -> None:
    """Bindings use fixed categories and never echo configured attributes."""
    assert _binding_kind(source) == expected


def test_source_group_projection_counts_every_quality_in_configured_order() -> None:
    """Quality and exclusion summaries retain all stable reason vocabularies."""
    sources = tuple(
        _temperature_source(
            index,
            entity_id=f"sensor.secret_{index}",
            enabled=index != len(SourceQuality) - 1,
        )
        for index, _quality in enumerate(SourceQuality)
    )
    observations = tuple(
        _observation(index, quality) for index, quality in enumerate(SourceQuality)
    )
    excluded = tuple(
        item for item in observations if item.quality is not SourceQuality.VALID
    )
    aggregation = SourceAggregationResult(
        effective_value=20.0,
        spread=0.0,
        valid_source_ids=(SOURCE_IDS[0],),
        contributing_source_ids=(SOURCE_IDS[0],),
        fallback_source_id=SOURCE_IDS[0],
        excluded_observations=excluded,
        status=AggregationStatus.DEGRADED,
        reasons=(
            AggregationReason.SOURCE_EXCLUDED,
            AggregationReason.OUTLIER_EXCLUDED,
            AggregationReason.TWO_SOURCE_CONTRADICTION,
            AggregationReason.PRIORITY_FALLBACK,
        ),
        calculated_at=NOW,
    )

    result = _source_group_projection(
        sources,
        observations,
        aggregation,
        _ReportPseudonymizer(b"a" * 32),
    )

    assert result["total_configured_sources"] == len(SourceQuality)
    assert result["enabled_sources"] == len(SourceQuality) - 1
    assert result["valid_sources"] == 1
    assert result["contributing_sources"] == 1
    assert result["excluded_sources"] == len(SourceQuality) - 1
    assert result["quality_counts"] == {quality.value: 1 for quality in SourceQuality}
    assert result["exclusion_reason_counts"] == {
        reason.value: 1 for reason in ExclusionReason
    }
    assert result["aggregation_status"] == "degraded"
    assert result["aggregation_reasons"] == [
        "source_excluded",
        "outlier_excluded",
        "two_source_contradiction",
        "priority_fallback",
    ]
    assert result["effective_value_available"] is True
    assert [row["source_id"] for row in result["sources"]] == [
        str(source.source_id) for source in sources
    ]
    assert result["sources"][0]["contributing"] is True
    assert result["sources"][0]["fallback"] is True
    restored_index = list(SourceQuality).index(SourceQuality.RESTORED_NOT_CONFIRMED)
    assert result["sources"][restored_index]["restored"] is True
    assert "private raw provider value" not in repr(result)
    assert all(
        re.fullmatch(r"entity_[0-9a-f]{12}", row["entity_reference"])
        for row in result["sources"]
    )


def test_source_group_projection_handles_unobserved_disabled_source() -> None:
    """Disabled or non-running sources remain bounded without fake quality."""
    source = _temperature_source(0, enabled=False)
    aggregation = SourceAggregationResult(
        effective_value=None,
        spread=None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=(),
        status=AggregationStatus.UNAVAILABLE,
        reasons=(AggregationReason.NO_ENABLED_SOURCES,),
        calculated_at=NOW,
    )

    result = _source_group_projection(
        (source,),
        (),
        aggregation,
        _ReportPseudonymizer(b"a" * 32),
    )

    assert result["enabled_sources"] == 0
    assert result["quality_counts"] == {quality.value: 0 for quality in SourceQuality}
    assert result["exclusion_reason_counts"] == {
        reason.value: 0 for reason in ExclusionReason
    }
    assert result["sources"][0]["quality"] is None
    assert result["sources"][0]["exclusion_reason"] is None
    assert result["sources"][0]["source_last_reported"] is None
    assert result["sources"][0]["observed_at"] is None
    assert result["sources"][0]["restored"] is None

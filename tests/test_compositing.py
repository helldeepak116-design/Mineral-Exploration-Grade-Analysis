
import numpy as np
import pandas as pd
import pytest

from src.compositing import (
    GRADE_COLUMNS,
    generate_composites,
)


@pytest.fixture
def assay_data():
    """Create a small synthetic assay dataset for testing."""

    return pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0.0, 2.0],
        "To_m": [2.0, 5.0],
        "Fe_pct": [10.0, 20.0],
        "SiO2_pct": [80.0, 70.0],
        "Al2O3_pct": [5.0, 6.0],
        "LOI_pct": [5.0, 4.0],
    })


def test_generate_single_composite(assay_data):
    """Verify one composite is generated for a complete interval."""

    result = generate_composites(
        assay_data,
        composite_length=5.0,
    )

    assert len(result) == 1
    assert result.iloc[0]["Hole_ID"] == "BH-001"
    assert result.iloc[0]["From_m"] == 0.0
    assert result.iloc[0]["To_m"] == 5.0
    assert result.iloc[0]["Thickness_m"] == 5.0


def test_length_weighted_grade_calculation(assay_data):
    """Verify grades are weighted by interval thickness."""

    result = generate_composites(
        assay_data,
        composite_length=5.0,
    )

    # (10 * 2 + 20 * 3) / 5 = 16
    assert result.iloc[0]["Fe_pct"] == pytest.approx(16.0)

    # (80 * 2 + 70 * 3) / 5 = 74
    assert result.iloc[0]["SiO2_pct"] == pytest.approx(74.0)

    # (5 * 2 + 6 * 3) / 5 = 5.6
    assert result.iloc[0]["Al2O3_pct"] == pytest.approx(5.6)

    # (5 * 2 + 4 * 3) / 5 = 4.4
    assert result.iloc[0]["LOI_pct"] == pytest.approx(4.4)


def test_partial_final_composite_is_retained():
    """Verify the final composite is retained when shorter than target."""

    assay = pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0.0, 3.0],
        "To_m": [3.0, 7.0],
        "Fe_pct": [10.0, 30.0],
        "SiO2_pct": [80.0, 60.0],
        "Al2O3_pct": [5.0, 7.0],
        "LOI_pct": [5.0, 3.0],
    })

    result = generate_composites(
        assay,
        composite_length=5.0,
    )

    assert len(result) == 2

    assert result.iloc[0]["From_m"] == 0.0
    assert result.iloc[0]["To_m"] == 5.0
    assert result.iloc[0]["Thickness_m"] == 5.0

    assert result.iloc[1]["From_m"] == 5.0
    assert result.iloc[1]["To_m"] == 7.0
    assert result.iloc[1]["Thickness_m"] == 2.0

    assert result.iloc[1]["Fe_pct"] == pytest.approx(30.0)


def test_multiple_drillholes_are_composited_independently():
    """Verify composites are generated separately for each hole."""

    assay = pd.DataFrame({
        "Hole_ID": ["BH-002", "BH-001"],
        "From_m": [0.0, 0.0],
        "To_m": [5.0, 5.0],
        "Fe_pct": [40.0, 60.0],
        "SiO2_pct": [50.0, 30.0],
        "Al2O3_pct": [5.0, 5.0],
        "LOI_pct": [5.0, 5.0],
    })

    result = generate_composites(assay, 5.0)

    assert len(result) == 2
    assert result["Hole_ID"].tolist() == ["BH-001", "BH-002"]

    assert result.iloc[0]["Fe_pct"] == pytest.approx(60.0)
    assert result.iloc[1]["Fe_pct"] == pytest.approx(40.0)


def test_composite_starts_at_first_sampled_depth():
    """Verify compositing does not automatically start at zero."""

    assay = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "From_m": [10.0],
        "To_m": [15.0],
        "Fe_pct": [55.0],
        "SiO2_pct": [30.0],
        "Al2O3_pct": [10.0],
        "LOI_pct": [5.0],
    })

    result = generate_composites(assay, 5.0)

    assert result.iloc[0]["From_m"] == 10.0
    assert result.iloc[0]["To_m"] == 15.0


def test_incomplete_assay_coverage_is_rejected():
    """Verify unsampled gaps are not silently extrapolated."""

    assay = pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0.0, 3.0],
        "To_m": [2.0, 5.0],
        "Fe_pct": [40.0, 50.0],
        "SiO2_pct": [50.0, 40.0],
        "Al2O3_pct": [5.0, 5.0],
        "LOI_pct": [5.0, 5.0],
    })

    with pytest.raises(ValueError, match="Incomplete assay coverage"):
        generate_composites(assay, 5.0)


def test_overlapping_assay_intervals_are_rejected():
    """Verify overlapping assay intervals raise an error."""

    assay = pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0.0, 2.0],
        "To_m": [3.0, 5.0],
        "Fe_pct": [40.0, 50.0],
        "SiO2_pct": [50.0, 40.0],
        "Al2O3_pct": [5.0, 5.0],
        "LOI_pct": [5.0, 5.0],
    })

    with pytest.raises(ValueError, match="Overlapping assay intervals"):
        generate_composites(assay, 5.0)


def test_missing_required_column_is_rejected(assay_data):
    """Verify missing assay columns are detected."""

    assay = assay_data.drop(columns=["Fe_pct"])

    with pytest.raises(ValueError, match="Missing required assay columns"):
        generate_composites(assay, 5.0)


def test_empty_assay_dataset_is_rejected(assay_data):
    """Verify an empty dataset raises an error."""

    assay = assay_data.iloc[0:0]

    with pytest.raises(ValueError, match="empty"):
        generate_composites(assay, 5.0)


@pytest.mark.parametrize(
    "composite_length",
    [0, -1, np.nan, np.inf, -np.inf],
)
def test_invalid_composite_length_is_rejected(
    assay_data,
    composite_length,
):
    """Verify invalid composite lengths are rejected."""

    with pytest.raises(ValueError):
        generate_composites(
            assay_data,
            composite_length,
        )


def test_non_numeric_composite_length_is_rejected(assay_data):
    """Verify a non-numeric composite length is rejected."""

    with pytest.raises(ValueError, match="must be numeric"):
        generate_composites(assay_data, "invalid")


def test_invalid_grade_values_are_rejected(assay_data):
    """Verify grades outside the 0-100 range are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = 105.0

    with pytest.raises(ValueError, match="between 0 and 100"):
        generate_composites(assay, 5.0)


def test_missing_grade_values_are_rejected(assay_data):
    """Verify missing assay grades are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = np.nan

    with pytest.raises(ValueError, match="non-finite"):
        generate_composites(assay, 5.0)


def test_infinite_grade_values_are_rejected(assay_data):
    """Verify infinite assay grades are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = np.inf

    with pytest.raises(ValueError, match="non-finite"):
        generate_composites(assay, 5.0)


def test_negative_assay_depth_is_rejected(assay_data):
    """Verify negative interval depths are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "From_m"] = -1.0

    with pytest.raises(ValueError, match="Negative assay depths"):
        generate_composites(assay, 5.0)


def test_zero_thickness_interval_is_rejected(assay_data):
    """Verify zero-thickness intervals are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "To_m"] = assay.loc[0, "From_m"]

    with pytest.raises(ValueError, match="positive thickness"):
        generate_composites(assay, 5.0)


def test_missing_hole_id_is_rejected(assay_data):
    """Verify missing drillhole identifiers are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "Hole_ID"] = None

    with pytest.raises(ValueError, match="missing values"):
        generate_composites(assay, 5.0)


def test_blank_hole_id_is_rejected(assay_data):
    """Verify blank drillhole identifiers are rejected."""

    assay = assay_data.copy()
    assay.loc[0, "Hole_ID"] = "   "

    with pytest.raises(ValueError, match="blank values"):
        generate_composites(assay, 5.0)


def test_original_assay_dataframe_is_not_modified(assay_data):
    """Verify compositing does not modify the source DataFrame."""

    original = assay_data.copy(deep=True)

    generate_composites(assay_data, 5.0)

    pd.testing.assert_frame_equal(assay_data, original)


def test_all_grade_columns_are_present_in_output(assay_data):
    """Verify every analyte is included in composite results."""

    result = generate_composites(assay_data, 5.0)

    for column in GRADE_COLUMNS:
        assert column in result.columns

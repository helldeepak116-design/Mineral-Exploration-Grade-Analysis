
import numpy as np
import pandas as pd
import pytest

from src.grade_analysis import (
    calculate_grade_statistics,
    calculate_weighted_grade,
    calculate_hole_grade_summary,
    calculate_grade_thickness,
    apply_cutoff_grade,
    calculate_lithology_grade_summary,
)


@pytest.fixture
def assay_data():
    return pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001", "BH-002"],
        "From_m": [0.0, 2.0, 0.0],
        "To_m": [2.0, 5.0, 4.0],
        "Fe_pct": [10.0, 20.0, 60.0],
        "SiO2_pct": [80.0, 70.0, 30.0],
    })


@pytest.fixture
def lithology_data():
    return pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001", "BH-002"],
        "From_m": [0.0, 2.0, 0.0],
        "To_m": [2.0, 5.0, 4.0],
        "Lithology": ["BHQ", "HEM", "HEM"],
    })


def test_calculate_grade_statistics(assay_data):
    result = calculate_grade_statistics(assay_data)

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(30.0)
    assert result["median"] == pytest.approx(20.0)
    assert result["minimum"] == pytest.approx(10.0)
    assert result["maximum"] == pytest.approx(60.0)
    assert result["std_dev"] == pytest.approx(
        np.std([10.0, 20.0, 60.0], ddof=1)
    )


def test_grade_statistics_with_custom_column(assay_data):
    result = calculate_grade_statistics(
        assay_data,
        "SiO2_pct",
    )

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(60.0)


def test_calculate_weighted_grade(assay_data):
    result = calculate_weighted_grade(assay_data)

    # (10*2 + 20*3 + 60*4) / 9 = 35.5556
    assert result == pytest.approx(320 / 9)


def test_weighted_grade_with_custom_column(assay_data):
    result = calculate_weighted_grade(
        assay_data,
        "SiO2_pct",
    )

    # (80*2 + 70*3 + 30*4) / 9 = 54.4444
    assert result == pytest.approx(490 / 9)


def test_calculate_hole_grade_summary(assay_data):
    result = calculate_hole_grade_summary(assay_data)

    assert len(result) == 2
    assert result["Hole_ID"].tolist() == ["BH-001", "BH-002"]

    bh001 = result.loc[
        result["Hole_ID"] == "BH-001"
    ].iloc[0]

    assert bh001["Total_Assayed_Length_m"] == pytest.approx(5.0)
    assert bh001["Weighted_Grade_pct"] == pytest.approx(16.0)


def test_hole_grade_summary_uses_interval_weights(assay_data):
    result = calculate_hole_grade_summary(assay_data)

    bh002 = result.loc[
        result["Hole_ID"] == "BH-002"
    ].iloc[0]

    assert bh002["Weighted_Grade_pct"] == pytest.approx(60.0)
    assert bh002["Total_Assayed_Length_m"] == pytest.approx(4.0)


def test_calculate_grade_thickness(assay_data):
    result = calculate_grade_thickness(assay_data)

    assert "Thickness_m" in result.columns
    assert "Grade_Thickness" in result.columns

    assert result["Thickness_m"].tolist() == [2.0, 3.0, 4.0]
    assert result["Grade_Thickness"].tolist() == [20.0, 60.0, 240.0]


def test_grade_thickness_with_custom_column(assay_data):
    result = calculate_grade_thickness(
        assay_data,
        "SiO2_pct",
    )

    assert result["Grade_Thickness"].tolist() == [160.0, 210.0, 120.0]


def test_apply_cutoff_grade(assay_data):
    result = apply_cutoff_grade(
        assay_data,
        cutoff_grade=20.0,
    )

    assert len(result) == 2
    assert result["Fe_pct"].tolist() == [20.0, 60.0]


def test_cutoff_includes_exact_threshold(assay_data):
    result = apply_cutoff_grade(
        assay_data,
        cutoff_grade=60.0,
    )

    assert len(result) == 1
    assert result.iloc[0]["Fe_pct"] == 60.0


def test_cutoff_zero_returns_all_valid_intervals(assay_data):
    result = apply_cutoff_grade(
        assay_data,
        cutoff_grade=0.0,
    )

    assert len(result) == len(assay_data)


def test_cutoff_100_returns_only_exact_100_grades(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = 100.0

    result = apply_cutoff_grade(
        assay,
        cutoff_grade=100.0,
    )

    assert len(result) == 1
    assert result.iloc[0]["Fe_pct"] == 100.0


def test_calculate_lithology_grade_summary(
    assay_data,
    lithology_data,
):
    result = calculate_lithology_grade_summary(
        assay_data,
        lithology_data,
    )

    assert set(result["Lithology"]) == {"BHQ", "HEM"}

    bhq = result.loc[
        result["Lithology"] == "BHQ"
    ].iloc[0]

    hem = result.loc[
        result["Lithology"] == "HEM"
    ].iloc[0]

    assert bhq["Total_Length_m"] == pytest.approx(2.0)
    assert bhq["Interval_Count"] == 1
    assert bhq["Weighted_Fe_Grade_pct"] == pytest.approx(10.0)

    assert hem["Total_Length_m"] == pytest.approx(7.0)
    assert hem["Interval_Count"] == 2
    assert hem["Weighted_Fe_Grade_pct"] == pytest.approx(
        300 / 7
    )


def test_empty_assay_is_rejected(assay_data):
    with pytest.raises(ValueError, match="empty"):
        calculate_grade_statistics(
            assay_data.iloc[0:0]
        )


def test_missing_grade_column_is_rejected(assay_data):
    assay = assay_data.drop(columns=["Fe_pct"])

    with pytest.raises(ValueError, match="Missing required columns"):
        calculate_grade_statistics(assay)


def test_invalid_grade_above_100_is_rejected(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = 101.0

    with pytest.raises(ValueError, match="between 0 and 100"):
        calculate_grade_statistics(assay)


def test_negative_grade_is_rejected(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = -1.0

    with pytest.raises(ValueError, match="between 0 and 100"):
        calculate_grade_statistics(assay)


def test_non_numeric_grade_is_rejected(assay_data):
    assay = assay_data.copy()
    assay["Fe_pct"] = assay["Fe_pct"].astype(object)
    assay.loc[0, "Fe_pct"] = "invalid"

    with pytest.raises(ValueError, match="non-finite"):
        calculate_grade_statistics(assay)


def test_infinite_grade_is_rejected(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "Fe_pct"] = np.inf

    with pytest.raises(ValueError, match="non-finite"):
        calculate_grade_statistics(assay)


def test_negative_interval_depth_is_rejected(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "From_m"] = -1.0

    with pytest.raises(ValueError, match="Negative assay depths"):
        calculate_weighted_grade(assay)


def test_zero_thickness_interval_is_rejected(assay_data):
    assay = assay_data.copy()
    assay.loc[0, "To_m"] = assay.loc[0, "From_m"]

    with pytest.raises(ValueError, match="positive thickness"):
        calculate_weighted_grade(assay)


@pytest.mark.parametrize(
    "cutoff",
    [-1, 101, np.nan, np.inf, -np.inf],
)
def test_invalid_cutoff_is_rejected(assay_data, cutoff):
    with pytest.raises(ValueError, match="between 0 and 100"):
        apply_cutoff_grade(assay_data, cutoff)


def test_non_numeric_cutoff_is_rejected(assay_data):
    with pytest.raises(ValueError, match="must be numeric"):
        apply_cutoff_grade(assay_data, "invalid")


def test_missing_lithology_column_is_rejected(
    assay_data,
    lithology_data,
):
    lithology = lithology_data.drop(columns=["Lithology"])

    with pytest.raises(ValueError, match="missing required columns"):
        calculate_lithology_grade_summary(
            assay_data,
            lithology,
        )


def test_empty_lithology_is_rejected(
    assay_data,
    lithology_data,
):
    with pytest.raises(ValueError, match="empty"):
        calculate_lithology_grade_summary(
            assay_data,
            lithology_data.iloc[0:0],
        )


def test_unmatched_lithology_intervals_are_rejected(
    assay_data,
    lithology_data,
):
    lithology = lithology_data.copy()
    lithology.loc[0, "To_m"] = 1.5

    with pytest.raises(ValueError, match="must match exactly"):
        calculate_lithology_grade_summary(
            assay_data,
            lithology,
        )


def test_duplicate_lithology_interval_keys_are_rejected(
    assay_data,
    lithology_data,
):
    lithology = pd.concat(
        [lithology_data, lithology_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate lithology"):
        calculate_lithology_grade_summary(
            assay_data,
            lithology,
        )


def test_duplicate_assay_interval_keys_are_rejected(
    assay_data,
    lithology_data,
):
    assay = pd.concat(
        [assay_data, assay_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate assay"):
        calculate_lithology_grade_summary(
            assay,
            lithology_data,
        )


def test_original_assay_is_not_modified(assay_data):
    original = assay_data.copy(deep=True)

    calculate_weighted_grade(assay_data)
    calculate_grade_statistics(assay_data)
    calculate_grade_thickness(assay_data)
    apply_cutoff_grade(assay_data, 20.0)

    pd.testing.assert_frame_equal(assay_data, original)

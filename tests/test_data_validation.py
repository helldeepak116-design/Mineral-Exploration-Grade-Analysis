
import copy

import pandas as pd
import pytest

from src.data_validation import (
    load_project_data,
    validate_assay_grades,
    validate_collar,
    validate_intervals,
    validate_project,
    validate_required_columns,
    validate_survey,
)


# ---------------------------------------------------------
# 1. SAMPLE DATA TESTS
# ---------------------------------------------------------

def test_sample_project_has_no_validation_errors():
    datasets = load_project_data("data/sample")

    issues = validate_project(datasets)

    assert issues == [], f"Validation issues found: {issues}"


def test_sample_data_contains_all_four_datasets():
    datasets = load_project_data("data/sample")

    assert set(datasets.keys()) == {
        "collar",
        "survey",
        "lithology",
        "assay",
    }


# ---------------------------------------------------------
# 2. REQUIRED COLUMN TESTS
# ---------------------------------------------------------

def test_detect_missing_dataset():
    datasets = load_project_data("data/sample")
    datasets.pop("survey")

    issues = validate_required_columns(datasets)

    assert any(
        "survey: dataset is missing" in issue
        for issue in issues
    )


def test_detect_missing_collar_column():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["collar"] = modified["collar"].drop(
        columns=["Easting"]
    )

    issues = validate_project(modified)

    assert any("Easting" in issue for issue in issues)


def test_detect_missing_survey_column():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["survey"] = modified["survey"].drop(
        columns=["Azimuth_deg"]
    )

    issues = validate_project(modified)

    assert any("Azimuth_deg" in issue for issue in issues)


def test_detect_missing_lithology_column():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["lithology"] = modified["lithology"].drop(
        columns=["Lithology"]
    )

    issues = validate_project(modified)

    assert any("Lithology" in issue for issue in issues)


def test_detect_missing_assay_column():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["assay"] = modified["assay"].drop(
        columns=["Fe_pct"]
    )

    issues = validate_project(modified)

    assert any("Fe_pct" in issue for issue in issues)


# ---------------------------------------------------------
# 3. COLLAR VALIDATION TESTS
# ---------------------------------------------------------

def test_detect_duplicate_drillhole_ids():
    datasets = load_project_data("data/sample")
    collar = datasets["collar"].copy()

    collar.loc[1, "Hole_ID"] = collar.loc[0, "Hole_ID"]

    issues = validate_collar(collar)

    assert any("duplicate Hole_ID" in issue for issue in issues)


def test_detect_non_numeric_collar_coordinates():
    datasets = load_project_data("data/sample")
    collar = datasets["collar"].copy()

    collar["Easting"] = collar["Easting"].astype(object)
    collar.loc[0, "Easting"] = "invalid"

    issues = validate_collar(collar)

    assert any("Easting" in issue for issue in issues)


def test_detect_zero_drillhole_depth():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["collar"].loc[0, "Total_Depth_m"] = 0

    issues = validate_project(modified)

    assert any(
        "greater than zero" in issue
        for issue in issues
    )


def test_detect_negative_drillhole_depth():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["collar"].loc[0, "Total_Depth_m"] = -10

    issues = validate_project(modified)

    assert any(
        "greater than zero" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 4. INTERVAL VALIDATION TESTS
# ---------------------------------------------------------

def test_detect_overlapping_intervals():
    collar = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "Total_Depth_m": [60],
    })

    intervals = pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0, 10],
        "To_m": [15, 20],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
        collar,
    )

    assert any(
        "overlapping intervals" in issue
        for issue in issues
    )


def test_detect_depth_gaps():
    collar = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "Total_Depth_m": [60],
    })

    intervals = pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001"],
        "From_m": [0, 20],
        "To_m": [10, 30],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
        collar,
    )

    assert any(
        "depth gap" in issue
        for issue in issues
    )


def test_detect_unknown_drillhole():
    collar = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "Total_Depth_m": [60],
    })

    intervals = pd.DataFrame({
        "Hole_ID": ["BH-999"],
        "From_m": [0],
        "To_m": [10],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
        collar,
    )

    assert any(
        "unknown drillhole" in issue
        for issue in issues
    )


def test_detect_negative_interval_start():
    intervals = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "From_m": [-5],
        "To_m": [10],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
    )

    assert any(
        "cannot be negative" in issue
        for issue in issues
    )


def test_detect_invalid_interval_order():
    intervals = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "From_m": [15],
        "To_m": [10],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
    )

    assert any(
        "greater than From_m" in issue
        for issue in issues
    )


def test_detect_interval_exceeding_total_depth():
    collar = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "Total_Depth_m": [60],
    })

    intervals = pd.DataFrame({
        "Hole_ID": ["BH-001"],
        "From_m": [50],
        "To_m": [65],
    })

    issues = validate_intervals(
        intervals,
        "lithology",
        collar,
    )

    assert any(
        "exceeds total depth" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 5. SURVEY VALIDATION TESTS
# ---------------------------------------------------------

def test_detect_invalid_survey_azimuth():
    datasets = load_project_data("data/sample")
    survey = datasets["survey"].copy()

    survey.loc[0, "Azimuth_deg"] = 361

    issues = validate_survey(
        survey,
        datasets["collar"],
    )

    assert any(
        "Azimuth_deg" in issue
        for issue in issues
    )


def test_detect_invalid_survey_dip():
    datasets = load_project_data("data/sample")
    survey = datasets["survey"].copy()

    survey.loc[0, "Dip_deg"] = -95

    issues = validate_survey(
        survey,
        datasets["collar"],
    )

    assert any(
        "Dip_deg" in issue
        for issue in issues
    )


def test_detect_negative_survey_depth():
    datasets = load_project_data("data/sample")
    survey = datasets["survey"].copy()

    survey.loc[0, "Depth_m"] = -1

    issues = validate_survey(
        survey,
        datasets["collar"],
    )

    assert any(
        "Depth_m" in issue
        for issue in issues
    )


def test_detect_survey_depth_exceeding_hole_depth():
    datasets = load_project_data("data/sample")
    survey = datasets["survey"].copy()

    survey.loc[0, "Depth_m"] = 100

    issues = validate_survey(
        survey,
        datasets["collar"],
    )

    assert any(
        "exceeds total depth" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 6. ASSAY GRADE VALIDATION TESTS
# ---------------------------------------------------------

def test_detect_grade_above_100():
    datasets = load_project_data("data/sample")
    assay = datasets["assay"].copy()

    assay.loc[0, "Fe_pct"] = 105

    issues = validate_assay_grades(assay)

    assert any(
        "Fe_pct" in issue
        for issue in issues
    )


def test_detect_negative_assay_grade():
    datasets = load_project_data("data/sample")
    assay = datasets["assay"].copy()

    assay.loc[0, "Fe_pct"] = -5

    issues = validate_assay_grades(assay)

    assert any(
        "Fe_pct" in issue
        for issue in issues
    )


def test_detect_non_numeric_assay_grade():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["assay"]["Fe_pct"] = (
        modified["assay"]["Fe_pct"].astype(object)
    )
    modified["assay"].loc[0, "Fe_pct"] = "invalid"

    issues = validate_project(modified)

    assert any(
        "Fe_pct" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 7. ASSAY-LITHOLOGY ALIGNMENT TESTS
# ---------------------------------------------------------

def test_detect_assay_lithology_interval_mismatch():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["assay"].loc[0, "To_m"] += 1

    issues = validate_project(modified)

    assert any(
        "intervals do not match" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 8. MISSING VALUE TESTS
# ---------------------------------------------------------

def test_detect_missing_collar_value():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["collar"]["Easting"] = (
        modified["collar"]["Easting"].astype(float)
    )
    modified["collar"].loc[0, "Easting"] = float("nan")

    issues = validate_project(modified)

    assert any(
        "Easting" in issue
        for issue in issues
    )


def test_detect_nan_survey_measurement():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["survey"]["Azimuth_deg"] = (
        modified["survey"]["Azimuth_deg"].astype(float)
    )
    modified["survey"].loc[0, "Azimuth_deg"] = float("nan")

    issues = validate_project(modified)

    assert any(
        "Azimuth_deg" in issue
        for issue in issues
    )


def test_detect_missing_assay_grade():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["assay"]["Fe_pct"] = (
        modified["assay"]["Fe_pct"].astype(float)
    )
    modified["assay"].loc[0, "Fe_pct"] = float("nan")

    issues = validate_project(modified)

    assert any(
        "Fe_pct" in issue
        for issue in issues
    )


# ---------------------------------------------------------
# 9. NON-FINITE VALUE TESTS
# ---------------------------------------------------------

def test_detect_infinite_collar_coordinate():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["collar"]["Easting"] = (
        modified["collar"]["Easting"].astype(object)
    )
    modified["collar"].loc[0, "Easting"] = float("inf")

    issues = validate_project(modified)

    assert any(
        "Easting" in issue
        for issue in issues
    )


def test_detect_infinite_assay_grade():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["assay"]["Fe_pct"] = (
        modified["assay"]["Fe_pct"].astype(float)
    )
    modified["assay"].loc[0, "Fe_pct"] = float("inf")

    issues = validate_project(modified)

    assert any(
        "Fe_pct" in issue
        for issue in issues
    )


def test_detect_negative_infinite_interval_depth():
    datasets = load_project_data("data/sample")
    modified = copy.deepcopy(datasets)

    modified["lithology"]["From_m"] = (
        modified["lithology"]["From_m"].astype(object)
    )
    modified["lithology"].loc[0, "From_m"] = float("-inf")

    issues = validate_project(modified)

    assert any(
        "From_m" in issue
        for issue in issues
    )


from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "collar": [
        "Hole_ID",
        "Easting",
        "Northing",
        "RL_m",
        "Total_Depth_m",
    ],
    "survey": [
        "Hole_ID",
        "Depth_m",
        "Azimuth_deg",
        "Dip_deg",
    ],
    "lithology": [
        "Hole_ID",
        "From_m",
        "To_m",
        "Lithology",
    ],
    "assay": [
        "Hole_ID",
        "From_m",
        "To_m",
        "Fe_pct",
        "SiO2_pct",
        "Al2O3_pct",
        "LOI_pct",
    ],
}

GRADE_COLUMNS = [
    "Fe_pct",
    "SiO2_pct",
    "Al2O3_pct",
    "LOI_pct",
]


def load_project_data(data_dir="data/sample"):
    """Load the four project CSV datasets."""

    data_path = Path(data_dir)

    filenames = {
        "collar": "collar.csv",
        "survey": "survey.csv",
        "lithology": "lithology.csv",
        "assay": "assay.csv",
    }

    datasets = {}

    for name, filename in filenames.items():
        file_path = data_path / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Required dataset not found: {file_path}"
            )

        datasets[name] = pd.read_csv(file_path)

    return datasets


def _numeric_values(series):
    """Convert values to numeric, replacing invalid entries with NaN."""

    return pd.to_numeric(
        series,
        errors="coerce",
    ).to_numpy(dtype=float, na_value=np.nan)


def _is_finite_column(df, column):
    """Return True when a column contains only finite numeric values."""

    if column not in df.columns:
        return False

    return bool(np.isfinite(_numeric_values(df[column])).all())


def validate_required_columns(datasets):
    """Check required datasets, columns and missing values."""

    issues = []

    for name, required in REQUIRED_COLUMNS.items():

        if name not in datasets:
            issues.append(f"{name}: dataset is missing")
            continue

        df = datasets[name]

        if not isinstance(df, pd.DataFrame):
            issues.append(f"{name}: dataset must be a DataFrame")
            continue

        if df.empty:
            issues.append(f"{name}: dataset is empty")
            continue

        missing_columns = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing_columns:
            issues.append(
                f"{name}: missing required columns: "
                f"{', '.join(missing_columns)}"
            )
            continue

        for column in required:
            if df[column].isna().any():
                issues.append(
                    f"{name}: missing values in {column}"
                )

    return issues


def validate_collar(collar):
    """Validate collar coordinates and drillhole total depths."""

    issues = []

    required = REQUIRED_COLUMNS["collar"]

    if not all(column in collar.columns for column in required):
        return issues

    numeric_columns = [
        "Easting",
        "Northing",
        "RL_m",
        "Total_Depth_m",
    ]

    for column in numeric_columns:

        if not _is_finite_column(collar, column):
            issues.append(
                f"collar: invalid numeric or non-finite values in {column}"
            )

    if any(
        not _is_finite_column(collar, column)
        for column in numeric_columns
    ):
        return issues

    if (collar["Total_Depth_m"] <= 0).any():
        issues.append(
            "collar: Total_Depth_m must be greater than zero"
        )

    if collar["Hole_ID"].duplicated().any():
        issues.append(
            "collar: duplicate Hole_ID values found"
        )

    return issues


def validate_intervals(df, dataset_name, collar=None):
    """
    Validate interval boundaries, overlaps, gaps and drillhole limits.

    collar is optional for compatibility with standalone interval checks.
    """

    issues = []

    required = [
        "Hole_ID",
        "From_m",
        "To_m",
    ]

    if not all(column in df.columns for column in required):
        return issues

    for column in ["From_m", "To_m"]:

        if not _is_finite_column(df, column):
            issues.append(
                f"{dataset_name}: invalid numeric or non-finite "
                f"values in {column}"
            )

    if (
        not _is_finite_column(df, "From_m")
        or not _is_finite_column(df, "To_m")
    ):
        return issues

    if (df["From_m"] < 0).any():
        issues.append(
            f"{dataset_name}: From_m cannot be negative"
        )

    if (df["To_m"] <= df["From_m"]).any():
        issues.append(
            f"{dataset_name}: To_m must be greater than From_m"
        )

    if collar is not None:

        if (
            "Hole_ID" in collar.columns
            and "Total_Depth_m" in collar.columns
            and _is_finite_column(collar, "Total_Depth_m")
        ):
            collar_depths = collar.set_index("Hole_ID")[
                "Total_Depth_m"
            ]

            for hole_id in df["Hole_ID"].unique():

                if hole_id not in collar_depths.index:
                    issues.append(
                        f"{dataset_name}: unknown drillhole {hole_id}"
                    )
                    continue

                hole_intervals = df[df["Hole_ID"] == hole_id]

                if (
                    hole_intervals["To_m"]
                    > collar_depths.loc[hole_id]
                ).any():
                    issues.append(
                        f"{dataset_name}: interval exceeds total depth "
                        f"for {hole_id}"
                    )

        else:
            issues.append(
                f"{dataset_name}: collar depth information is unavailable"
            )

    for hole_id, group in df.groupby("Hole_ID"):

        group = group.sort_values("From_m")

        previous_to = None

        for _, row in group.iterrows():

            current_from = float(row["From_m"])
            current_to = float(row["To_m"])

            if previous_to is not None:

                if current_from < previous_to:
                    issues.append(
                        f"{dataset_name}: overlapping intervals "
                        f"found in {hole_id}"
                    )
                    break

                if current_from > previous_to:
                    issues.append(
                        f"{dataset_name}: depth gap found in {hole_id}"
                    )
                    break

            previous_to = current_to

    return issues


def validate_survey(survey, collar):
    """Validate downhole survey measurements."""

    issues = []

    required = REQUIRED_COLUMNS["survey"]

    if not all(column in survey.columns for column in required):
        return issues

    numeric_columns = [
        "Depth_m",
        "Azimuth_deg",
        "Dip_deg",
    ]

    for column in numeric_columns:

        if not _is_finite_column(survey, column):
            issues.append(
                f"survey: invalid numeric or non-finite values in {column}"
            )

    if any(
        not _is_finite_column(survey, column)
        for column in numeric_columns
    ):
        return issues

    if (survey["Depth_m"] < 0).any():
        issues.append(
            "survey: Depth_m cannot be negative"
        )

    if (
        (survey["Azimuth_deg"] < 0)
        | (survey["Azimuth_deg"] >= 360)
    ).any():
        issues.append(
            "survey: Azimuth_deg must be between 0 and less than 360"
        )

    if (
        (survey["Dip_deg"] < -90)
        | (survey["Dip_deg"] > 90)
    ).any():
        issues.append(
            "survey: Dip_deg must be between -90 and 90"
        )

    if (
        "Hole_ID" not in collar.columns
        or "Total_Depth_m" not in collar.columns
        or not _is_finite_column(collar, "Total_Depth_m")
    ):
        issues.append(
            "survey: collar total-depth information is unavailable"
        )
        return issues

    collar_depths = collar.set_index("Hole_ID")["Total_Depth_m"]

    for _, row in survey.iterrows():

        hole_id = row["Hole_ID"]

        if hole_id not in collar_depths.index:
            issues.append(
                f"survey: unknown Hole_ID {hole_id}"
            )
            continue

        if row["Depth_m"] > collar_depths.loc[hole_id]:
            issues.append(
                f"survey: survey depth exceeds total depth "
                f"for {hole_id}"
            )

    return issues


def validate_assay_grades(assay):
    """Validate assay grade values and numeric ranges."""

    issues = []

    for column in GRADE_COLUMNS:

        if column not in assay.columns:
            continue

        values = _numeric_values(assay[column])

        if not np.isfinite(values).all():
            issues.append(
                f"assay: invalid numeric or non-finite values in {column}"
            )
            continue

        if ((values < 0) | (values > 100)).any():
            issues.append(
                f"assay: {column} values must be between 0 and 100"
            )

    return issues


def validate_interval_alignment(lithology, assay):
    """Check whether assay and lithology intervals match."""

    required = [
        "Hole_ID",
        "From_m",
        "To_m",
    ]

    if not all(column in lithology.columns for column in required):
        return []

    if not all(column in assay.columns for column in required):
        return []

    for df in [lithology, assay]:

        for column in ["From_m", "To_m"]:

            if not _is_finite_column(df, column):
                return []

    lithology_intervals = set(
        zip(
            lithology["Hole_ID"],
            lithology["From_m"].astype(float),
            lithology["To_m"].astype(float),
        )
    )

    assay_intervals = set(
        zip(
            assay["Hole_ID"],
            assay["From_m"].astype(float),
            assay["To_m"].astype(float),
        )
    )

    if lithology_intervals != assay_intervals:
        return [
            "Assay and lithology intervals do not match"
        ]

    return []


def validate_project(datasets):
    """Run all validation checks on the complete project."""

    issues = validate_required_columns(datasets)

    if issues:
        return issues

    collar = datasets["collar"]
    survey = datasets["survey"]
    lithology = datasets["lithology"]
    assay = datasets["assay"]

    collar_issues = validate_collar(collar)
    issues.extend(collar_issues)

    if collar_issues:
        return issues

    issues.extend(
        validate_intervals(
            lithology,
            "lithology",
            collar,
        )
    )

    issues.extend(
        validate_intervals(
            assay,
            "assay",
            collar,
        )
    )

    issues.extend(
        validate_survey(
            survey,
            collar,
        )
    )

    issues.extend(
        validate_assay_grades(assay)
    )

    issues.extend(
        validate_interval_alignment(
            lithology,
            assay,
        )
    )

    return issues

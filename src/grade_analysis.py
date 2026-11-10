
import numpy as np
import pandas as pd


def _validate_grade_data(
    assay: pd.DataFrame,
    grade_column: str,
    require_intervals: bool = True,
) -> pd.DataFrame:
    """Validate assay grades and, optionally, interval boundaries."""

    if not isinstance(assay, pd.DataFrame):
        raise TypeError("Assay input must be a pandas DataFrame.")

    if assay.empty:
        raise ValueError("Assay dataset is empty.")

    required = {"Hole_ID", grade_column}

    if require_intervals:
        required.update({"From_m", "To_m"})

    missing = required - set(assay.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = assay.copy()

    if data["Hole_ID"].isna().any():
        raise ValueError("Hole_ID contains missing values.")

    data["Hole_ID"] = data["Hole_ID"].astype(str).str.strip()

    if data["Hole_ID"].eq("").any():
        raise ValueError("Hole_ID contains blank values.")

    numeric_columns = [grade_column]

    if require_intervals:
        numeric_columns.extend(["From_m", "To_m"])

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    values = data[numeric_columns].to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError(
            "Assay data contains missing, non-numeric or non-finite values."
        )

    if not data[grade_column].between(0, 100).all():
        raise ValueError(
            f"{grade_column} values must be between 0 and 100."
        )

    if require_intervals:

        if (data["From_m"] < 0).any():
            raise ValueError("Negative assay depths are not allowed.")

        if (data["To_m"] <= data["From_m"]).any():
            raise ValueError(
                "Assay intervals must have positive thickness."
            )

    return data


def calculate_grade_statistics(
    assay: pd.DataFrame,
    grade_column: str = "Fe_pct",
) -> dict:
    """Calculate descriptive statistics for an assay grade."""

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=False,
    )

    grades = data[grade_column]

    return {
        "count": int(grades.count()),
        "mean": float(grades.mean()),
        "median": float(grades.median()),
        "std_dev": float(grades.std()),
        "minimum": float(grades.min()),
        "maximum": float(grades.max()),
    }


def calculate_weighted_grade(
    assay: pd.DataFrame,
    grade_column: str = "Fe_pct",
) -> float:
    """
    Calculate the dataset-wide length-weighted average grade.

    This is an interval-length-weighted grade, not a tonnage-weighted
    resource grade.
    """

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=True,
    )

    thickness = data["To_m"] - data["From_m"]

    return float(
        np.average(
            data[grade_column].to_numpy(dtype=float),
            weights=thickness.to_numpy(dtype=float),
        )
    )


def calculate_hole_grade_summary(
    assay: pd.DataFrame,
    grade_column: str = "Fe_pct",
) -> pd.DataFrame:
    """Calculate length-weighted grade separately for each drillhole."""

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=True,
    )

    records = []

    for hole_id, group in data.groupby("Hole_ID", sort=True):

        thickness = group["To_m"] - group["From_m"]

        total_length = float(thickness.sum())

        weighted_grade = float(
            np.average(
                group[grade_column].to_numpy(dtype=float),
                weights=thickness.to_numpy(dtype=float),
            )
        )

        records.append({
            "Hole_ID": hole_id,
            "Total_Assayed_Length_m": total_length,
            "Weighted_Grade_pct": weighted_grade,
        })

    return pd.DataFrame(records)


def calculate_grade_thickness(
    assay: pd.DataFrame,
    grade_column: str = "Fe_pct",
) -> pd.DataFrame:
    """
    Calculate interval-level grade-thickness.

    Grade-thickness is grade (%) multiplied by interval thickness (m).
    It is not tonnage or contained metal.
    """

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=True,
    )

    result = data.copy()

    result["Thickness_m"] = (
        result["To_m"] - result["From_m"]
    )

    result["Grade_Thickness"] = (
        result[grade_column] * result["Thickness_m"]
    )

    return result


def apply_cutoff_grade(
    assay: pd.DataFrame,
    cutoff_grade: float,
    grade_column: str = "Fe_pct",
) -> pd.DataFrame:
    """Filter assay intervals using a grade cut-off."""

    if not np.isscalar(cutoff_grade):
        raise TypeError("Cut-off grade must be numeric.")

    try:
        cutoff_grade = float(cutoff_grade)
    except (TypeError, ValueError):
        raise ValueError("Cut-off grade must be numeric.")

    if not np.isfinite(cutoff_grade) or not 0 <= cutoff_grade <= 100:
        raise ValueError(
            "Cut-off grade must be between 0 and 100."
        )

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=False,
    )

    return data.loc[
        data[grade_column] >= cutoff_grade
    ].copy()


def calculate_lithology_grade_summary(
    assay: pd.DataFrame,
    lithology: pd.DataFrame,
    grade_column: str = "Fe_pct",
) -> pd.DataFrame:
    """Calculate length-weighted assay grades by lithological unit."""

    if not isinstance(lithology, pd.DataFrame):
        raise TypeError("Lithology input must be a pandas DataFrame.")

    if lithology.empty:
        raise ValueError("Lithology dataset is empty.")

    required_lithology = {
        "Hole_ID",
        "From_m",
        "To_m",
        "Lithology",
    }

    missing_lithology = (
        required_lithology - set(lithology.columns)
    )

    if missing_lithology:
        raise ValueError(
            "Lithology table is missing required columns: "
            f"{sorted(missing_lithology)}"
        )

    data = _validate_grade_data(
        assay,
        grade_column,
        require_intervals=True,
    )

    lith = lithology.copy()

    if lith["Hole_ID"].isna().any():
        raise ValueError("Lithology Hole_ID contains missing values.")

    if lith["Lithology"].isna().any():
        raise ValueError("Lithology contains missing unit names.")

    lith["Hole_ID"] = lith["Hole_ID"].astype(str).str.strip()
    lith["Lithology"] = lith["Lithology"].astype(str).str.strip()

    if lith["Hole_ID"].eq("").any() or lith["Lithology"].eq("").any():
        raise ValueError("Lithology contains blank identifiers or unit names.")

    for column in ["From_m", "To_m"]:
        lith[column] = pd.to_numeric(
            lith[column],
            errors="coerce",
        )

    lith_values = lith[
        ["From_m", "To_m"]
    ].to_numpy(dtype=float)

    if not np.isfinite(lith_values).all():
        raise ValueError(
            "Lithology intervals contain missing or non-finite values."
        )

    if (lith["From_m"] < 0).any():
        raise ValueError("Lithology From_m cannot be negative.")

    if (lith["To_m"] <= lith["From_m"]).any():
        raise ValueError("Lithology intervals must have positive thickness.")

    keys = ["Hole_ID", "From_m", "To_m"]

    if lith.duplicated(subset=keys).any():
        raise ValueError("Duplicate lithology interval keys found.")

    if data.duplicated(subset=keys).any():
        raise ValueError("Duplicate assay interval keys found.")

    merged = lith.merge(
        data[keys + [grade_column]],
        on=keys,
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(lith) or len(merged) != len(data):
        raise ValueError(
            "Assay and lithology intervals must match exactly."
        )

    merged["Thickness_m"] = (
        merged["To_m"] - merged["From_m"]
    )

    merged["Grade_Thickness"] = (
        merged[grade_column] * merged["Thickness_m"]
    )

    summary = merged.groupby("Lithology").agg(
        Total_Length_m=("Thickness_m", "sum"),
        Total_Grade_Thickness=("Grade_Thickness", "sum"),
        Interval_Count=("Lithology", "size"),
    ).reset_index()

    summary["Weighted_Fe_Grade_pct"] = (
        summary["Total_Grade_Thickness"]
        / summary["Total_Length_m"]
    )

    return summary

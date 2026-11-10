
import numpy as np
import pandas as pd


GRADE_COLUMNS = [
    "Fe_pct",
    "SiO2_pct",
    "Al2O3_pct",
    "LOI_pct",
]


def generate_composites(
    assay: pd.DataFrame,
    composite_length: float = 5.0,
) -> pd.DataFrame:
    """
    Generate fixed-length, length-weighted assay composites.

    Compositing begins at the first sampled From_m depth for each hole.
    Partial final composites are retained.

    Overlapping intervals, invalid grades and incomplete assay coverage
    are rejected. No grades are extrapolated into unsampled intervals.
    """

    if not isinstance(assay, pd.DataFrame):
        raise TypeError("Assay input must be a pandas DataFrame.")

    if not np.isscalar(composite_length):
        raise TypeError("Composite length must be a numeric scalar.")

    try:
        composite_length = float(composite_length)
    except (TypeError, ValueError):
        raise ValueError("Composite length must be numeric.")

    if not np.isfinite(composite_length) or composite_length <= 0:
        raise ValueError(
            "Composite length must be a finite value greater than zero."
        )

    required = {
        "Hole_ID",
        "From_m",
        "To_m",
        *GRADE_COLUMNS,
    }

    missing = required - set(assay.columns)

    if missing:
        raise ValueError(
            f"Missing required assay columns: {sorted(missing)}"
        )

    if assay.empty:
        raise ValueError("Assay dataset is empty.")

    data = assay.copy()

    # Validate drillhole identifiers.
    if data["Hole_ID"].isna().any():
        raise ValueError("Hole_ID contains missing values.")

    data["Hole_ID"] = data["Hole_ID"].astype(str).str.strip()

    if data["Hole_ID"].eq("").any():
        raise ValueError("Hole_ID contains blank values.")

    # Convert numeric columns.
    numeric_columns = [
        "From_m",
        "To_m",
        *GRADE_COLUMNS,
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    # Reject NaN, infinity and non-numeric values.
    numeric_values = data[numeric_columns].to_numpy(dtype=float)

    if not np.isfinite(numeric_values).all():
        raise ValueError(
            "Assay data contains missing, non-numeric or non-finite values."
        )

    # Validate interval boundaries.
    if (data["From_m"] < 0).any():
        raise ValueError(
            "Negative assay depths are not allowed."
        )

    if (data["To_m"] <= data["From_m"]).any():
        raise ValueError(
            "Assay intervals must have positive thickness."
        )

    # Validate assay grades.
    if not data[GRADE_COLUMNS].apply(
        lambda column: column.between(0, 100).all()
    ).all():
        raise ValueError(
            "Assay grades must be between 0 and 100."
        )

    records = []

    for hole_id, group in data.groupby("Hole_ID", sort=True):

        group = (
            group.sort_values("From_m")
            .reset_index(drop=True)
        )

        from_depths = group["From_m"].to_numpy(dtype=float)
        to_depths = group["To_m"].to_numpy(dtype=float)

        # Reject overlapping assay intervals.
        if len(group) > 1:

            if np.any(
                from_depths[1:] < to_depths[:-1] - 1e-10
            ):
                raise ValueError(
                    f"Overlapping assay intervals in {hole_id}."
                )

        hole_start = float(from_depths[0])
        hole_end = float(to_depths[-1])

        composite_start = hole_start

        while composite_start < hole_end - 1e-10:

            composite_end = min(
                composite_start + composite_length,
                hole_end,
            )

            overlap_start = np.maximum(
                from_depths,
                composite_start,
            )

            overlap_end = np.minimum(
                to_depths,
                composite_end,
            )

            overlap = np.maximum(
                0.0,
                overlap_end - overlap_start,
            )

            covered_length = float(overlap.sum())

            composite_thickness = (
                composite_end - composite_start
            )

            # Ensure the entire composite interval is sampled.
            if not np.isclose(
                covered_length,
                composite_thickness,
                rtol=1e-9,
                atol=1e-8,
            ):
                raise ValueError(
                    f"Incomplete assay coverage in {hole_id}: "
                    f"{composite_start:.2f}-{composite_end:.2f} m."
                )

            record = {
                "Hole_ID": hole_id,
                "From_m": round(composite_start, 4),
                "To_m": round(composite_end, 4),
                "Thickness_m": round(
                    composite_thickness,
                    4,
                ),
            }

            # Calculate length-weighted grade for each analyte.
            for column in GRADE_COLUMNS:

                grades = group[column].to_numpy(dtype=float)

                weighted_grade = np.average(
                    grades,
                    weights=overlap,
                )

                record[column] = float(weighted_grade)

            records.append(record)

            composite_start = composite_end

    return pd.DataFrame(records)

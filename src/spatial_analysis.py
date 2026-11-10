
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _validate_collar_record(collar: pd.DataFrame, hole_id: str) -> pd.Series:
    """Validate and return exactly one collar record for a drillhole."""

    required = {
        "Hole_ID", "Easting", "Northing", "RL_m", "Total_Depth_m"
    }

    if not isinstance(collar, pd.DataFrame):
        raise TypeError("Collar data must be a pandas DataFrame.")

    missing = required.difference(collar.columns)
    if missing:
        raise ValueError(
            f"Collar dataset is missing columns: {sorted(missing)}"
        )

    if collar.empty:
        raise ValueError("Collar dataset is empty.")

    rows = collar.loc[collar["Hole_ID"] == hole_id]

    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one collar record for {hole_id}; "
            f"found {len(rows)}."
        )

    row = rows.iloc[0]

    for column in ["Easting", "Northing", "RL_m", "Total_Depth_m"]:
        value = pd.to_numeric(row[column], errors="coerce")

        if pd.isna(value) or not np.isfinite(value):
            raise ValueError(
                f"{hole_id}: {column} must be a finite numeric value."
            )

    if float(row["Total_Depth_m"]) <= 0:
        raise ValueError(
            f"{hole_id}: total depth must be greater than zero."
        )

    return row


def calculate_drillhole_trace(
    collar: pd.DataFrame,
    survey: pd.DataFrame,
    hole_id: str,
    step_m: float = 5.0,
) -> pd.DataFrame:
    """
    Calculate a simplified straight drillhole trace.

    Uses the first survey station and assumes constant azimuth and dip.
    Azimuth is clockwise from north; negative dip is downward.

    This is not a survey-corrected drillhole trajectory.
    """

    if (
        isinstance(step_m, (bool, np.bool_))
        or not isinstance(step_m, (int, float, np.integer, np.floating))
        or not np.isfinite(step_m)
        or step_m <= 0
    ):
        raise ValueError("Step length must be a finite positive number.")

    collar_row = _validate_collar_record(collar, hole_id)
    total_depth = float(collar_row["Total_Depth_m"])

    if not isinstance(survey, pd.DataFrame):
        raise TypeError("Survey data must be a pandas DataFrame.")

    required = {"Hole_ID", "Depth_m", "Azimuth_deg", "Dip_deg"}
    missing = required.difference(survey.columns)

    if missing:
        raise ValueError(
            f"Survey dataset is missing columns: {sorted(missing)}"
        )

    hole_survey = survey.loc[
        survey["Hole_ID"] == hole_id
    ].copy()

    if hole_survey.empty:
        raise ValueError(f"No survey data found for {hole_id}.")

    for column in ["Depth_m", "Azimuth_deg", "Dip_deg"]:
        hole_survey[column] = pd.to_numeric(
            hole_survey[column], errors="coerce"
        )

        if not np.isfinite(
            hole_survey[column].to_numpy(dtype=float)
        ).all():
            raise ValueError(
                f"{hole_id}: survey column {column} "
                "contains invalid numeric values."
            )

    hole_survey = hole_survey.sort_values(
        "Depth_m"
    ).reset_index(drop=True)

    if hole_survey["Depth_m"].duplicated().any():
        raise ValueError(
            f"{hole_id}: duplicate survey station depths found."
        )

    if not np.isclose(hole_survey["Depth_m"].iloc[0], 0.0):
        raise ValueError(
            f"{hole_id}: survey must contain a station at 0 m."
        )

    if (
        (hole_survey["Depth_m"] < 0).any()
        or (hole_survey["Depth_m"] > total_depth).any()
    ):
        raise ValueError(
            f"{hole_id}: survey station depths must be "
            "within the drillhole depth."
        )

    if (
        (hole_survey["Azimuth_deg"] < 0).any()
        or (hole_survey["Azimuth_deg"] > 360).any()
    ):
        raise ValueError(
            f"{hole_id}: azimuth must be between 0 and 360 degrees."
        )

    if (
        (hole_survey["Dip_deg"] < -90).any()
        or (hole_survey["Dip_deg"] > 90).any()
    ):
        raise ValueError(
            f"{hole_id}: dip must be between -90 and 90 degrees."
        )

    # Simplification: use only the first survey station.
    azimuth = float(hole_survey["Azimuth_deg"].iloc[0])
    dip = float(hole_survey["Dip_deg"].iloc[0])

    depths = np.arange(0.0, total_depth, float(step_m))
    depths = np.append(depths, total_depth)

    azimuth_rad = np.radians(azimuth)
    dip_rad = np.radians(dip)

    easting = (
        float(collar_row["Easting"])
        + depths * np.cos(dip_rad) * np.sin(azimuth_rad)
    )

    northing = (
        float(collar_row["Northing"])
        + depths * np.cos(dip_rad) * np.cos(azimuth_rad)
    )

    elevation = (
        float(collar_row["RL_m"])
        + depths * np.sin(dip_rad)
    )

    return pd.DataFrame({
        "Hole_ID": hole_id,
        "Depth_m": depths,
        "Easting": easting,
        "Northing": northing,
        "RL_m": elevation,
    })


def plot_collar_locations(collar: pd.DataFrame):
    """Create an interactive 2D drillhole collar location map."""

    if not isinstance(collar, pd.DataFrame):
        raise TypeError("Collar data must be a pandas DataFrame.")

    required = {"Hole_ID", "Easting", "Northing"}
    missing = required.difference(collar.columns)

    if missing:
        raise ValueError(
            f"Collar dataset is missing columns: {sorted(missing)}"
        )

    if collar.empty:
        raise ValueError("Collar dataset is empty.")

    plot_data = collar.copy()

    for column in ["Easting", "Northing"]:
        plot_data[column] = pd.to_numeric(
            plot_data[column], errors="coerce"
        )

        if not np.isfinite(
            plot_data[column].to_numpy(dtype=float)
        ).all():
            raise ValueError(
                f"Collar column {column} contains invalid coordinates."
            )

    hover_columns = [
        column for column in ["RL_m", "Total_Depth_m"]
        if column in plot_data.columns
    ]

    figure = px.scatter(
        plot_data,
        x="Easting",
        y="Northing",
        text="Hole_ID",
        hover_data=hover_columns,
        title="Drill-Hole Collar Location Map",
        labels={
            "Easting": "Easting (m)",
            "Northing": "Northing (m)",
        },
    )

    figure.update_traces(
        marker=dict(size=12, symbol="circle"),
        textposition="top center",
        textfont=dict(size=12),
    )

    figure.update_xaxes(
        tickformat=",.0f",
        exponentformat="none",
        showexponent="none",
        showgrid=True,
        zeroline=False,
    )

    figure.update_yaxes(
        tickformat=",.0f",
        exponentformat="none",
        showexponent="none",
        showgrid=True,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )

    figure.update_layout(
        height=550,
        template="plotly_dark",
        margin=dict(l=30, r=30, t=70, b=40),
        hovermode="closest",
    )

    return figure


def plot_drillhole_traces(
    collar: pd.DataFrame,
    survey: pd.DataFrame,
    step_m: float = 5.0,
):
    """Create an improved 3D visualization of simplified drillhole traces."""

    if not isinstance(collar, pd.DataFrame):
        raise TypeError("Collar data must be a pandas DataFrame.")

    if "Hole_ID" not in collar.columns:
        raise ValueError("Collar dataset must contain Hole_ID.")

    if collar.empty:
        raise ValueError("Collar dataset is empty.")

    if collar["Hole_ID"].isna().any():
        raise ValueError("Collar dataset contains missing Hole_ID values.")

    if collar["Hole_ID"].duplicated().any():
        raise ValueError("Collar dataset contains duplicate Hole_ID values.")

    figure = go.Figure()

    for hole_id in collar["Hole_ID"]:
        trace = calculate_drillhole_trace(
            collar, survey, hole_id, step_m
        )

        figure.add_trace(
            go.Scatter3d(
                x=trace["Easting"],
                y=trace["Northing"],
                z=trace["RL_m"],
                mode="lines+markers",
                name=hole_id,
                line=dict(width=7),
                marker=dict(size=3),
                customdata=trace[["Depth_m"]],
                hovertemplate=(
                    "Hole: " + hole_id
                    + "<br>Depth: %{customdata[0]:.1f} m"
                    + "<br>Easting: %{x:,.2f} m"
                    + "<br>Northing: %{y:,.2f} m"
                    + "<br>RL: %{z:.2f} m"
                    + "<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        title="3D Drill-Hole Trace Visualization",
        height=750,
        template="plotly_dark",
        margin=dict(l=0, r=0, t=70, b=0),
        legend=dict(
            title="Drillhole",
            orientation="v",
        ),
        scene={
            "xaxis": {
                "title": "Easting (m)",
                "tickformat": ",.0f",
                "exponentformat": "none",
            },
            "yaxis": {
                "title": "Northing (m)",
                "tickformat": ",.0f",
                "exponentformat": "none",
            },
            "zaxis": {
                "title": "RL (m)",
                "tickformat": ".1f",
            },
            "aspectmode": "data",
            "camera": {
                "eye": {"x": 1.7, "y": 1.7, "z": 1.3},
            },
        },
    )

    return figure

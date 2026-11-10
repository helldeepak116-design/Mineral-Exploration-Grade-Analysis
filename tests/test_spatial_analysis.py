
import numpy as np
import pandas as pd
import pytest

from src.spatial_analysis import (
    calculate_drillhole_trace,
    plot_collar_locations,
    plot_drillhole_traces,
)


@pytest.fixture
def collar_data():
    return pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-002"],
        "Easting": [500000.0, 500050.0],
        "Northing": [2400000.0, 2400025.0],
        "RL_m": [125.5, 128.0],
        "Total_Depth_m": [60.0, 55.0],
    })


@pytest.fixture
def survey_data():
    return pd.DataFrame({
        "Hole_ID": ["BH-001", "BH-001", "BH-002", "BH-002"],
        "Depth_m": [0.0, 60.0, 0.0, 55.0],
        "Azimuth_deg": [90.0, 90.0, 90.0, 90.0],
        "Dip_deg": [-60.0, -60.0, -60.0, -60.0],
    })


def test_trace_starts_at_collar_coordinates(collar_data, survey_data):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-001",
    )

    first = result.iloc[0]

    assert first["Depth_m"] == pytest.approx(0.0)
    assert first["Easting"] == pytest.approx(500000.0)
    assert first["Northing"] == pytest.approx(2400000.0)
    assert first["RL_m"] == pytest.approx(125.5)


def test_trace_reaches_total_drillhole_depth(collar_data, survey_data):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-001",
    )

    last = result.iloc[-1]

    assert last["Depth_m"] == pytest.approx(60.0)


def test_eastward_trace_for_90_degree_azimuth(
    collar_data,
    survey_data,
):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-001",
    )

    # At 5 m depth, horizontal displacement is 5*cos(60°) = 2.5 m.
    row = result.loc[result["Depth_m"] == 5.0].iloc[0]

    assert row["Easting"] == pytest.approx(500002.5)
    assert row["Northing"] == pytest.approx(2400000.0)


def test_downward_elevation_for_negative_60_dip(
    collar_data,
    survey_data,
):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-001",
    )

    # Vertical displacement at 5 m = 5*sin(-60°).
    row = result.loc[result["Depth_m"] == 5.0].iloc[0]

    assert row["RL_m"] == pytest.approx(
        125.5 - 5.0 * np.sin(np.radians(60.0))
    )


def test_vertical_drillhole_trace(collar_data, survey_data):
    survey = survey_data.copy()
    survey.loc[survey["Hole_ID"] == "BH-001", "Dip_deg"] = -90.0

    result = calculate_drillhole_trace(
        collar_data,
        survey,
        "BH-001",
    )

    assert np.allclose(result["Easting"], 500000.0)
    assert np.allclose(result["Northing"], 2400000.0)
    assert result.iloc[-1]["RL_m"] == pytest.approx(65.5)


def test_northward_trace_for_zero_azimuth(collar_data, survey_data):
    survey = survey_data.copy()
    survey.loc[survey["Hole_ID"] == "BH-001", "Azimuth_deg"] = 0.0

    result = calculate_drillhole_trace(
        collar_data,
        survey,
        "BH-001",
    )

    row = result.loc[result["Depth_m"] == 5.0].iloc[0]

    assert row["Easting"] == pytest.approx(500000.0)
    assert row["Northing"] == pytest.approx(2400002.5)


def test_trace_uses_requested_drillhole(collar_data, survey_data):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-002",
    )

    assert result["Hole_ID"].eq("BH-002").all()
    assert result.iloc[0]["Easting"] == pytest.approx(500050.0)
    assert result.iloc[0]["Northing"] == pytest.approx(2400025.0)


def test_custom_step_length(collar_data, survey_data):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-001",
        step_m=10.0,
    )

    assert result["Depth_m"].tolist() == [
        0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0
    ]


def test_partial_final_step_is_retained(collar_data, survey_data):
    result = calculate_drillhole_trace(
        collar_data,
        survey_data,
        "BH-002",
        step_m=10.0,
    )

    assert result.iloc[-1]["Depth_m"] == pytest.approx(55.0)


def test_duplicate_collar_records_are_rejected(collar_data, survey_data):
    collar = pd.concat(
        [collar_data, collar_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="exactly one collar"):
        calculate_drillhole_trace(
            collar,
            survey_data,
            "BH-001",
        )


def test_missing_collar_record_is_rejected(collar_data, survey_data):
    with pytest.raises(ValueError, match="exactly one collar"):
        calculate_drillhole_trace(
            collar_data,
            survey_data,
            "BH-999",
        )


def test_missing_survey_data_is_rejected(collar_data, survey_data):
    survey = survey_data.loc[
        survey_data["Hole_ID"] != "BH-001"
    ]

    with pytest.raises(ValueError, match="No survey data"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


def test_survey_must_start_at_zero(collar_data, survey_data):
    survey = survey_data.copy()
    survey = survey.loc[
        ~(
            (survey["Hole_ID"] == "BH-001")
            & (survey["Depth_m"] == 0.0)
        )
    ]

    with pytest.raises(ValueError, match="station at 0 m"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


def test_invalid_azimuth_is_rejected(collar_data, survey_data):
    survey = survey_data.copy()
    survey.loc[0, "Azimuth_deg"] = 361.0

    with pytest.raises(ValueError, match="azimuth must be"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


def test_invalid_dip_is_rejected(collar_data, survey_data):
    survey = survey_data.copy()
    survey.loc[0, "Dip_deg"] = -91.0

    with pytest.raises(ValueError, match="dip must be"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


def test_survey_depth_beyond_hole_depth_is_rejected(
    collar_data,
    survey_data,
):
    survey = survey_data.copy()
    survey.loc[1, "Depth_m"] = 61.0

    with pytest.raises(ValueError, match="within the drillhole depth"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


def test_duplicate_survey_station_depth_is_rejected(
    collar_data,
    survey_data,
):
    survey = survey_data.copy()
    survey.loc[1, "Depth_m"] = 0.0

    with pytest.raises(ValueError, match="duplicate survey station"):
        calculate_drillhole_trace(
            collar_data,
            survey,
            "BH-001",
        )


@pytest.mark.parametrize(
    "step",
    [0, -1, np.nan, np.inf, -np.inf],
)
def test_invalid_step_length_is_rejected(
    collar_data,
    survey_data,
    step,
):
    with pytest.raises(ValueError, match="finite positive"):
        calculate_drillhole_trace(
            collar_data,
            survey_data,
            "BH-001",
            step_m=step,
        )


def test_missing_collar_column_is_rejected(collar_data, survey_data):
    collar = collar_data.drop(columns=["Easting"])

    with pytest.raises(ValueError, match="missing columns"):
        calculate_drillhole_trace(
            collar,
            survey_data,
            "BH-001",
        )


def test_non_finite_collar_coordinate_is_rejected(
    collar_data,
    survey_data,
):
    collar = collar_data.copy()
    collar.loc[0, "Easting"] = np.inf

    with pytest.raises(ValueError, match="finite numeric"):
        calculate_drillhole_trace(
            collar,
            survey_data,
            "BH-001",
        )


def test_zero_total_depth_is_rejected(collar_data, survey_data):
    collar = collar_data.copy()
    collar.loc[0, "Total_Depth_m"] = 0.0

    with pytest.raises(ValueError, match="greater than zero"):
        calculate_drillhole_trace(
            collar,
            survey_data,
            "BH-001",
        )


def test_collar_map_creates_plotly_figure(collar_data):
    figure = plot_collar_locations(collar_data)

    assert len(figure.data) == 1
    assert list(figure.data[0].text) == ["BH-001", "BH-002"]
    assert figure.layout.height == 550


def test_collar_map_uses_full_coordinate_tick_format(collar_data):
    figure = plot_collar_locations(collar_data)

    assert figure.layout.xaxis.tickformat == ",.0f"
    assert figure.layout.yaxis.tickformat == ",.0f"


def test_collar_map_rejects_empty_dataset(collar_data):
    with pytest.raises(ValueError, match="empty"):
        plot_collar_locations(collar_data.iloc[0:0])


def test_collar_map_rejects_missing_columns(collar_data):
    collar = collar_data.drop(columns=["Northing"])

    with pytest.raises(ValueError, match="missing columns"):
        plot_collar_locations(collar)


def test_collar_map_rejects_non_finite_coordinates(collar_data):
    collar = collar_data.copy()
    collar.loc[0, "Northing"] = np.nan

    with pytest.raises(ValueError, match="invalid coordinates"):
        plot_collar_locations(collar)


def test_3d_plot_contains_all_drillholes(collar_data, survey_data):
    figure = plot_drillhole_traces(
        collar_data,
        survey_data,
    )

    assert len(figure.data) == 2
    assert [trace.name for trace in figure.data] == [
        "BH-001",
        "BH-002",
    ]


def test_3d_plot_has_expected_height(collar_data, survey_data):
    figure = plot_drillhole_traces(
        collar_data,
        survey_data,
    )

    assert figure.layout.height == 750


def test_3d_plot_contains_depth_hover_information(
    collar_data,
    survey_data,
):
    figure = plot_drillhole_traces(
        collar_data,
        survey_data,
    )

    assert all(
        trace.customdata is not None
        for trace in figure.data
    )

    assert all(
        "Depth:" in trace.hovertemplate
        for trace in figure.data
    )


def test_3d_plot_rejects_duplicate_collar_ids(
    collar_data,
    survey_data,
):
    collar = pd.concat(
        [collar_data, collar_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="duplicate Hole_ID"):
        plot_drillhole_traces(
            collar,
            survey_data,
        )

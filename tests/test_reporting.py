
import io

import pandas as pd
import pytest
from openpyxl import load_workbook

from src.reporting import generate_excel_report
from src.data_validation import load_project_data


@pytest.fixture
def sample_datasets():
    return load_project_data("data/sample")


@pytest.fixture
def report_bytes(sample_datasets):
    return generate_excel_report(sample_datasets)


def test_report_returns_bytes(sample_datasets):
    result = generate_excel_report(sample_datasets)

    assert isinstance(result, bytes)
    assert len(result) > 0


def test_report_is_valid_excel_workbook(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))

    assert workbook is not None
    assert len(workbook.sheetnames) == 8


def test_report_contains_all_expected_sheets(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))

    expected_sheets = [
        "Collar_Data",
        "Survey_Data",
        "Lithology_Data",
        "Assay_Data",
        "Composite_Results",
        "Drillhole_Grade_Summary",
        "Lithology_Grade_Summary",
        "Grade_Statistics",
    ]

    assert workbook.sheetnames == expected_sheets


def test_raw_data_sheets_contain_expected_records(
    report_bytes, sample_datasets
):
    workbook = load_workbook(io.BytesIO(report_bytes))

    expected_sheets = {
        "Collar_Data": "collar",
        "Survey_Data": "survey",
        "Lithology_Data": "lithology",
        "Assay_Data": "assay",
    }

    for sheet_name, dataset_name in expected_sheets.items():
        worksheet = workbook[sheet_name]

        assert worksheet.max_row == len(
            sample_datasets[dataset_name]
        ) + 1


def test_composite_results_contain_36_records(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Composite_Results"]

    assert worksheet.max_row == 37


def test_composite_results_have_expected_headers(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Composite_Results"]

    headers = [
        cell.value
        for cell in worksheet[1]
    ]

    assert headers == [
        "Hole_ID",
        "From_m",
        "To_m",
        "Thickness_m",
        "Fe_pct",
        "SiO2_pct",
        "Al2O3_pct",
        "LOI_pct",
    ]


def test_all_sheets_have_frozen_header_rows(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))

    for worksheet in workbook.worksheets:
        assert worksheet.freeze_panes == "A2"


def test_all_sheets_have_auto_filters(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))

    for worksheet in workbook.worksheets:
        assert worksheet.auto_filter.ref is not None


def test_header_formatting_is_applied(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Collar_Data"]

    header_cell = worksheet["A1"]

    assert header_cell.font.bold is True
    assert header_cell.font.color.type == "rgb"
    assert header_cell.font.color.rgb[-6:] == "FFFFFF"
    assert header_cell.fill.fgColor.rgb == "001F4E78"


def test_grade_statistics_contains_expected_columns(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Grade_Statistics"]

    headers = [
        cell.value
        for cell in worksheet[1]
    ]

    assert headers == ["Statistic", "Value"]


def test_grade_statistics_contains_expected_statistics(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Grade_Statistics"]

    statistics = {
        worksheet.cell(row, 1).value:
        worksheet.cell(row, 2).value
        for row in range(2, worksheet.max_row + 1)
    }

    expected_statistics = {
        "count",
        "mean",
        "median",
        "std_dev",
        "minimum",
        "maximum",
    }

    assert expected_statistics.issubset(statistics.keys())


def test_grade_statistics_count_matches_assay_records(report_bytes):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Grade_Statistics"]

    statistics = {
        worksheet.cell(row, 1).value:
        worksheet.cell(row, 2).value
        for row in range(2, worksheet.max_row + 1)
    }

    assert statistics["count"] == 15


def test_empty_dataset_dictionary_is_rejected():
    with pytest.raises(ValueError):
        generate_excel_report({})


def test_non_dictionary_input_is_rejected():
    with pytest.raises((TypeError, ValueError)):
        generate_excel_report(None)


def test_missing_required_dataset_is_rejected(sample_datasets):
    incomplete_datasets = sample_datasets.copy()
    del incomplete_datasets["assay"]

    with pytest.raises((KeyError, ValueError)):
        generate_excel_report(incomplete_datasets)


def test_non_dataframe_dataset_is_rejected(sample_datasets):
    invalid_datasets = sample_datasets.copy()
    invalid_datasets["assay"] = ["invalid", "data"]

    with pytest.raises((TypeError, ValueError)):
        generate_excel_report(invalid_datasets)


def test_empty_dataframe_is_rejected(sample_datasets):
    invalid_datasets = sample_datasets.copy()
    invalid_datasets["assay"] = pd.DataFrame(
        columns=sample_datasets["assay"].columns
    )

    with pytest.raises(ValueError):
        generate_excel_report(invalid_datasets)


def test_exported_collar_data_matches_source(
    report_bytes, sample_datasets
):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Collar_Data"]

    exported_ids = [
        worksheet.cell(row, 1).value
        for row in range(2, worksheet.max_row + 1)
    ]

    assert exported_ids == sample_datasets["collar"]["Hole_ID"].tolist()


def test_exported_assay_data_matches_source(
    report_bytes, sample_datasets
):
    workbook = load_workbook(io.BytesIO(report_bytes))
    worksheet = workbook["Assay_Data"]

    exported_headers = [
        cell.value
        for cell in worksheet[1]
    ]

    assert exported_headers == sample_datasets["assay"].columns.tolist()

    exported_fe = [
        worksheet.cell(row, 4).value
        for row in range(2, worksheet.max_row + 1)
    ]

    assert exported_fe == pytest.approx(
        sample_datasets["assay"]["Fe_pct"].tolist()
    )

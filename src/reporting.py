
from io import BytesIO

import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.grade_analysis import (
    calculate_grade_statistics,
    calculate_hole_grade_summary,
    calculate_lithology_grade_summary,
)
from src.compositing import generate_composites


def _validate_report_datasets(datasets):
    """Validate the datasets required to generate the Excel report."""

    if not isinstance(datasets, dict):
        raise TypeError("Datasets must be provided as a dictionary.")

    required = {
        "collar",
        "survey",
        "lithology",
        "assay",
    }

    missing = required.difference(datasets)

    if missing:
        raise ValueError(
            f"Missing required datasets: {sorted(missing)}"
        )

    for name in required:
        if not isinstance(datasets[name], pd.DataFrame):
            raise TypeError(
                f"Dataset '{name}' must be a pandas DataFrame."
            )

        if datasets[name].empty:
            raise ValueError(
                f"Dataset '{name}' is empty."
            )


def _format_worksheet(worksheet):
    """Apply consistent formatting to an Excel worksheet."""

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    header_font = Font(
        name="Arial",
        size=10,
        bold=True,
        color="FFFFFF",
    )

    body_font = Font(
        name="Arial",
        size=10,
        color="202020",
    )

    thin_border = Border(
        bottom=Side(
            style="thin",
            color="D9E2F3",
        )
    )

    # Format header row.
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )
        cell.border = thin_border

    worksheet.row_dimensions[1].height = 24

    # Format data rows.
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = body_font
            cell.alignment = Alignment(
                vertical="center",
            )

    # Freeze headers and enable filtering.
    worksheet.freeze_panes = "A2"

    if worksheet.max_row > 0 and worksheet.max_column > 0:
        worksheet.auto_filter.ref = worksheet.dimensions

    # Set practical column widths.
    for column_cells in worksheet.columns:
        column_letter = get_column_letter(
            column_cells[0].column
        )

        max_length = max(
            (
                len(str(cell.value))
                if cell.value is not None
                else 0
            )
            for cell in column_cells
        )

        worksheet.column_dimensions[column_letter].width = min(
            max(max_length + 3, 12),
            35,
        )

    # Format percentage and numerical columns.
    for column_cells in worksheet.columns:
        header = str(column_cells[0].value).lower()

        if (
            header.endswith("_pct")
            or header in {"mean", "median", "std_dev", "min", "max"}
        ):
            for cell in column_cells[1:]:
                cell.number_format = "0.00"

        elif (
            header.endswith("_m")
            or header in {"easting", "northing", "rl_m"}
        ):
            for cell in column_cells[1:]:
                cell.number_format = "0.00"


def generate_excel_report(datasets) -> bytes:
    """
    Generate a formatted multi-sheet Excel report.

    The workbook contains raw geological datasets, 5 m
    downhole composites, grade summaries, and Fe statistics.

    Results are based on the supplied data and are not
    mineral resource or reserve estimates.
    """

    _validate_report_datasets(datasets)

    collar = datasets["collar"].copy()
    survey = datasets["survey"].copy()
    lithology = datasets["lithology"].copy()
    assay = datasets["assay"].copy()

    composites = generate_composites(
        assay,
        composite_length=5.0,
    )

    hole_summary = calculate_hole_grade_summary(
        assay
    )

    lithology_summary = calculate_lithology_grade_summary(
        assay,
        lithology,
    )

    statistics = calculate_grade_statistics(
        assay,
        "Fe_pct",
    )

    statistics_df = pd.DataFrame(
        list(statistics.items()),
        columns=["Statistic", "Value"],
    )

    sheets = {
        "Collar_Data": collar,
        "Survey_Data": survey,
        "Lithology_Data": lithology,
        "Assay_Data": assay,
        "Composite_Results": composites,
        "Drillhole_Grade_Summary": hole_summary,
        "Lithology_Grade_Summary": lithology_summary,
        "Grade_Statistics": statistics_df,
    }

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        for sheet_name, dataframe in sheets.items():
            dataframe.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

            worksheet = writer.sheets[sheet_name]

            _format_worksheet(worksheet)

    output.seek(0)

    return output.getvalue()


import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from src.data_validation import load_project_data, validate_project
from src.compositing import generate_composites
from src.grade_analysis import (
    calculate_grade_statistics,
    calculate_hole_grade_summary,
    calculate_grade_thickness,
    calculate_lithology_grade_summary,
    apply_cutoff_grade,
)
from src.spatial_analysis import (
    plot_collar_locations,
    plot_drillhole_traces,
)
from src.reporting import generate_excel_report


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Mineral Exploration Grade Analysis Toolkit",
    page_icon="⛏️",
    layout="wide",
)

st.title("⛏️ Mineral Exploration & Ore Grade Analysis Toolkit")

st.markdown(
    """
    An interactive geological exploration toolkit for:

    - Drillhole dataset validation
    - Downhole assay compositing
    - Iron ore grade analysis
    - Lithology-wise grade analysis
    - 2D and 3D drillhole visualization
    - Excel exploration report generation
    """
)

st.warning(
    "**Scientific disclaimer:** The bundled datasets are synthetic "
    "and hypothetical. They do not represent actual Bolani mine data. "
    "Analytical outputs are not mineral resource or reserve estimates."
)


# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select Module",
    [
        "Project Overview",
        "Data Validation",
        "Grade Analysis",
        "Compositing",
        "Spatial Visualization",
        "Report Export",
    ],
)

st.sidebar.divider()

source = st.sidebar.radio(
    "Data Source",
    [
        "Bundled Sample Data",
        "Upload My Datasets",
    ],
)


# ---------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------

@st.cache_data
def load_sample_data():
    return load_project_data("data/sample")


def read_uploaded_file(uploaded_file):
    """Read a CSV or Excel geological dataset."""

    if uploaded_file is None:
        raise ValueError("No file was supplied.")

    filename = uploaded_file.name.lower()

    try:
        uploaded_file.seek(0)

        if filename.endswith(".csv"):
            dataframe = pd.read_csv(uploaded_file)

        elif filename.endswith((".xlsx", ".xls")):
            dataframe = pd.read_excel(uploaded_file)

        else:
            raise ValueError(
                f"Unsupported file format: {uploaded_file.name}"
            )

    except Exception as error:
        raise ValueError(
            f"Could not read {uploaded_file.name}: {error}"
        ) from error

    if dataframe.empty:
        raise ValueError(
            f"{uploaded_file.name} contains no data rows."
        )

    return dataframe


def get_dataset_fingerprint(datasets):
    """Generate a fingerprint for the currently selected datasets."""

    digest = hashlib.sha256()

    for name in ["collar", "survey", "lithology", "assay"]:
        dataframe = datasets[name]

        digest.update(name.encode("utf-8"))
        digest.update(
            pd.util.hash_pandas_object(
                dataframe,
                index=True,
            ).values.tobytes()
        )

        digest.update(
            str(list(dataframe.columns)).encode("utf-8")
        )

    return digest.hexdigest()


# ---------------------------------------------------------
# SELECT DATA SOURCE
# ---------------------------------------------------------

if source == "Bundled Sample Data":

    try:
        datasets = load_sample_data()

    except Exception as error:
        st.error(
            f"Unable to load bundled sample datasets: {error}"
        )
        st.stop()

else:

    st.header("Upload Geological Exploration Datasets")

    st.info(
        "Upload all four datasets. CSV and Excel formats are supported. "
        "Column names must follow the required project schema."
    )

    col1, col2 = st.columns(2)

    with col1:
        collar_file = st.file_uploader(
            "Collar Dataset",
            type=["csv", "xlsx", "xls"],
            key="collar_upload",
        )

        survey_file = st.file_uploader(
            "Survey Dataset",
            type=["csv", "xlsx", "xls"],
            key="survey_upload",
        )

    with col2:
        lithology_file = st.file_uploader(
            "Lithology Dataset",
            type=["csv", "xlsx", "xls"],
            key="lithology_upload",
        )

        assay_file = st.file_uploader(
            "Assay Dataset",
            type=["csv", "xlsx", "xls"],
            key="assay_upload",
        )

    uploaded_files = {
        "collar": collar_file,
        "survey": survey_file,
        "lithology": lithology_file,
        "assay": assay_file,
    }

    if not all(uploaded_files.values()):
        st.warning(
            "Please upload all four datasets to continue."
        )
        st.stop()

    try:
        datasets = {
            name: read_uploaded_file(file)
            for name, file in uploaded_files.items()
        }

        validation_issues = validate_project(datasets)

        if validation_issues:
            st.error(
                f"Dataset validation failed: "
                f"{len(validation_issues)} issue(s) detected."
            )

            for issue in validation_issues:
                st.warning(issue)

            st.stop()

        st.success(
            "All four uploaded datasets passed validation."
        )

        with st.expander("Preview uploaded datasets"):
            for name, dataframe in datasets.items():
                st.subheader(name.capitalize())
                st.dataframe(
                    dataframe.head(10),
                    use_container_width=True,
                )

    except Exception as error:
        st.error(
            f"Unable to process uploaded datasets: {error}"
        )
        st.stop()


# ---------------------------------------------------------
# DATA REFERENCES
# ---------------------------------------------------------

collar = datasets["collar"]
survey = datasets["survey"]
lithology = datasets["lithology"]
assay = datasets["assay"]

dataset_fingerprint = get_dataset_fingerprint(datasets)


# Clear an old report when the source data changes.
if (
    st.session_state.get("report_fingerprint")
    != dataset_fingerprint
):
    st.session_state.pop("excel_report", None)
    st.session_state.pop("report_fingerprint", None)


# ---------------------------------------------------------
# PROJECT OVERVIEW
# ---------------------------------------------------------

if page == "Project Overview":

    st.header("Project Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Drillholes",
        len(collar),
    )

    col2.metric(
        "Lithology Intervals",
        len(lithology),
    )

    col3.metric(
        "Assay Intervals",
        len(assay),
    )

    col4.metric(
        "Total Drilled Depth",
        f"{collar['Total_Depth_m'].sum():.1f} m",
    )

    st.subheader("Drillhole Collar Information")

    st.dataframe(
        collar,
        use_container_width=True,
    )

    st.subheader("Assay Dataset")

    st.dataframe(
        assay,
        use_container_width=True,
    )

    st.subheader("Dataset Summary")

    summary = pd.DataFrame(
        {
            "Dataset": [
                "Collar",
                "Survey",
                "Lithology",
                "Assay",
            ],
            "Records": [
                len(collar),
                len(survey),
                len(lithology),
                len(assay),
            ],
        }
    )

    st.dataframe(
        summary,
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------
# DATA VALIDATION
# ---------------------------------------------------------

elif page == "Data Validation":

    st.header("Geological Data Validation")

    issues = validate_project(datasets)

    if issues:

        st.error(
            f"{len(issues)} validation issue(s) detected."
        )

        for issue in issues:
            st.warning(issue)

    else:

        st.success(
            "All current datasets passed validation."
        )

    st.subheader("Validation Summary")

    validation_summary = pd.DataFrame(
        {
            "Dataset": [
                "Collar",
                "Survey",
                "Lithology",
                "Assay",
            ],
            "Records": [
                len(collar),
                len(survey),
                len(lithology),
                len(assay),
            ],
        }
    )

    st.dataframe(
        validation_summary,
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------
# GRADE ANALYSIS
# ---------------------------------------------------------

elif page == "Grade Analysis":

    st.header("Iron Ore Grade Analysis")

    try:

        statistics = calculate_grade_statistics(
            assay,
            "Fe_pct",
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Mean Fe",
            f"{statistics['mean']:.2f}%",
        )

        col2.metric(
            "Median Fe",
            f"{statistics['median']:.2f}%",
        )

        col3.metric(
            "Minimum Fe",
            f"{statistics['minimum']:.2f}%",
        )

        col4.metric(
            "Maximum Fe",
            f"{statistics['maximum']:.2f}%",
        )

        st.subheader("Drillhole Grade Summary")

        hole_summary = calculate_hole_grade_summary(
            assay
        )

        st.dataframe(
            hole_summary,
            use_container_width=True,
        )

        st.subheader("Lithology-wise Grade Analysis")

        lithology_summary = calculate_lithology_grade_summary(
            assay,
            lithology,
        )

        st.dataframe(
            lithology_summary,
            use_container_width=True,
        )

        st.subheader("Cut-off Grade Analysis")

        cutoff = st.slider(
            "Select minimum Fe grade (%)",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=1.0,
        )

        selected = apply_cutoff_grade(
            assay,
            cutoff,
        )

        st.metric(
            "Intervals at or above cut-off",
            len(selected),
        )

        st.dataframe(
            selected,
            use_container_width=True,
        )

        st.subheader("Grade-Thickness Analysis")

        grade_thickness = calculate_grade_thickness(
            assay
        )

        st.dataframe(
            grade_thickness,
            use_container_width=True,
        )

        st.caption(
            "Grade-thickness is calculated as Fe grade (%) "
            "multiplied by downhole interval thickness (m). "
            "It is not contained-metal content or a resource estimate."
        )

        st.info(
            "Grade summaries are interval-length-weighted, "
            "not tonnage-weighted."
        )

    except Exception as error:
        st.error(
            f"Grade analysis could not be completed: {error}"
        )


# ---------------------------------------------------------
# ASSAY COMPOSITING
# ---------------------------------------------------------

elif page == "Compositing":

    st.header("Downhole Assay Compositing")

    composite_length = st.selectbox(
        "Composite Length (m)",
        [1.0, 2.0, 2.5, 5.0, 10.0],
        index=3,
    )

    try:

        composites = generate_composites(
            assay,
            composite_length=composite_length,
        )

        st.metric(
            "Generated Composites",
            len(composites),
        )

        st.dataframe(
            composites,
            use_container_width=True,
        )

        csv_data = composites.to_csv(
            index=False,
        ).encode("utf-8")

        st.download_button(
            label="Download Composite CSV",
            data=csv_data,
            file_name="composite_assay_results.csv",
            mime="text/csv",
        )

        st.caption(
            "Composites are length-weighted downhole intervals. "
            "Partial final composites are retained where applicable."
        )

    except Exception as error:
        st.error(
            f"Compositing could not be completed: {error}"
        )


# ---------------------------------------------------------
# SPATIAL VISUALIZATION
# ---------------------------------------------------------

elif page == "Spatial Visualization":

    st.header("Drillhole Spatial Visualization")

    try:

        st.subheader("2D Collar Location Map")

        collar_figure = plot_collar_locations(
            collar
        )

        st.plotly_chart(
            collar_figure,
            use_container_width=True,
        )

        st.subheader("3D Drillhole Traces")

        st.info(
            "The current 3D visualization assumes constant "
            "azimuth and dip using the first survey station. "
            "It is not a survey-corrected drillhole trajectory."
        )

        trace_figure = plot_drillhole_traces(
            collar,
            survey,
        )

        st.plotly_chart(
            trace_figure,
            use_container_width=True,
        )

    except Exception as error:
        st.error(
            f"Spatial visualization could not be generated: {error}"
        )


# ---------------------------------------------------------
# EXCEL REPORT EXPORT
# ---------------------------------------------------------

elif page == "Report Export":

    st.header("Exploration Data Report")

    st.markdown(
        """
        Generate a multi-sheet Excel workbook containing:

        1. Collar data
        2. Survey data
        3. Lithology intervals
        4. Assay records
        5. Five-metre composite results
        6. Drillhole grade summaries
        7. Lithology grade summaries
        8. Iron-grade statistics
        """
    )

    st.info(
        "The report uses the currently selected dataset source. "
        "Its composite interval is fixed at 5 metres."
    )

    if st.button(
        "Generate Excel Report",
        type="primary",
    ):

        try:

            report = generate_excel_report(
                datasets
            )

            # Confirm the generated file is a readable workbook.
            workbook = pd.ExcelFile(
                BytesIO(report),
                engine="openpyxl",
            )

            if len(workbook.sheet_names) != 8:
                raise ValueError(
                    "The generated workbook does not contain "
                    "the expected eight worksheets."
                )

            st.session_state["excel_report"] = report
            st.session_state["report_fingerprint"] = (
                dataset_fingerprint
            )

            st.success(
                "Excel report generated and verified successfully."
            )

        except Exception as error:
            st.error(
                f"Report generation failed: {error}"
            )

    if (
        "excel_report" in st.session_state
        and st.session_state.get("report_fingerprint")
        == dataset_fingerprint
    ):

        st.download_button(
            label="Download Excel Report",
            data=st.session_state["excel_report"],
            file_name="mineral_exploration_grade_report.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


# ---------------------------------------------------------
# SIDEBAR FOOTER
# ---------------------------------------------------------

st.sidebar.divider()

st.sidebar.caption(
    "Mineral Exploration Grade Analysis Toolkit"
)

st.sidebar.caption(
    "Synthetic demonstration dataset | Not a resource estimate"
)

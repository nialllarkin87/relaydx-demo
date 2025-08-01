import streamlit as st
from ingest.hl7_parser import parse_hl7
from ingest.csv_parser import parse_csv
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_output
from db import get_session
from models import LabResult
from sqlmodel import select
from main import save_result  # <— import the helper

st.set_page_config(page_title="RelayDX Demo UI", layout="wide")
st.title("🔬 RelayDX Demo Interface")
st.markdown("Upload an HL7 or CSV file to see parsing, normalization, persistence, and FHIR output in real time.")
st.markdown("---")

# Sidebar: Filters & Pagination for Persisted Results
st.sidebar.header("📋 Persisted Results Filters")
patient_filter = st.sidebar.text_input("Patient ID")
test_filter    = st.sidebar.text_input("Test Name Substring")
page_size      = st.sidebar.number_input("Page size", min_value=1, max_value=50, value=10)
page           = st.sidebar.number_input("Page number", min_value=1, value=1)
if st.sidebar.button("Apply Filters"):
    pass  # triggers rerun

# Query and display persisted results
with get_session() as session:
    query = select(LabResult)
    if patient_filter:
        query = query.where(LabResult.patient_id == patient_filter)
    if test_filter:
        query = query.where(LabResult.test_name.contains(test_filter))
    offset = (page - 1) * page_size
    results = session.exec(query.offset(offset).limit(page_size)).all()

st.subheader("📊 Persisted Lab Results")
if results:
    # Deprecation warning fix: use model_dump() instead of dict()
    df = [r.model_dump() for r in results]
    st.dataframe(df)
else:
    st.info("No records found for the given filters.")

st.markdown("---")

# File upload & real-time parsing (+ persistence)
uploaded_file = st.file_uploader("📂 Choose HL7 (.txt/.hl7) or CSV file", type=["txt","hl7","csv"])
if uploaded_file:
    content = uploaded_file.read().decode("utf-8")
    name = uploaded_file.name.lower()

    # HL7 branch
    if name.endswith((".hl7",".txt")):
        st.subheader("HL7 Parsing")
        try:
            raw = parse_hl7(content)
            st.json(raw)
            norm = normalize_result(raw)

            # Persist and show ID
            rec = save_result(norm)
            st.success(f"Persisted HL7 record with ID: {rec.id}")

            st.subheader("Normalized Result")
            st.json(norm)
            st.subheader("FHIR Output")
            st.json(build_fhir_output(norm))
        except Exception as e:
            st.error(f"Error parsing or saving HL7: {e}")

    # CSV branch
    elif name.endswith(".csv"):
        st.subheader("CSV Parsing")
        try:
            raws = parse_csv(content)
            st.json(raws)

            norms = [normalize_result(r) for r in raws]
            # Persist each record
            persisted_ids = []
            for norm in norms:
                rec = save_result(norm)
                persisted_ids.append(rec.id)
            st.success(f"Persisted CSV records with IDs: {persisted_ids}")

            st.subheader("Normalized Results")
            st.json(norms)
            st.subheader("FHIR Outputs")
            for n in norms:
                st.json(build_fhir_output(n))

        except Exception as e:
            st.error(f"Error parsing or saving CSV: {e}")

    else:
        st.warning("Unsupported file type. Upload .hl7/.txt or .csv.")


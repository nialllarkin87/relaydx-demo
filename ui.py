import streamlit as st
from ingest.hl7_parser import parse_hl7
from ingest.csv_parser import parse_csv
from normalize.transformer import normalize_result
from output.fhir_builder import build_fhir_output
from db import get_session, init_db
from models import LabResult
from sqlmodel import select
from main import save_result
import logging
import json

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization failed: {e}")

st.set_page_config(page_title="RelayDX Demo UI", layout="wide")
st.title("🔬 RelayDX Demo Interface")
st.markdown("Upload an HL7, CSV, or JSON file to see parsing, normalization, persistence, and FHIR output in real time.")
st.markdown("---")

# Sidebar: Filters & Pagination for Persisted Results
st.sidebar.header("📋 Persisted Results Filters")
patient_filter = st.sidebar.text_input("Patient ID")
test_filter = st.sidebar.text_input("Test Name Substring")
page_size = st.sidebar.number_input("Page size", min_value=1, max_value=50, value=10)
page = st.sidebar.number_input("Page number", min_value=1, value=1)

# Query and display persisted results
try:
    with get_session() as session:
        query = select(LabResult)
        if patient_filter:
            query = query.where(LabResult.patient_id.contains(patient_filter))
        if test_filter:
            query = query.where(LabResult.test_name.contains(test_filter))
        offset = (page - 1) * page_size
        results = session.exec(query.offset(offset).limit(page_size)).all()

    st.subheader("📊 Persisted Lab Results")
    if results:
        # Convert to dict for display
        df = []
        for r in results:
            df.append({
                "ID": r.id,
                "Patient ID": r.patient_id,
                "Test Code": r.test_code,
                "Test Name": r.test_name,
                "Result Value": r.result_value,
                "Units": r.units,
                "Collection Date": r.collection_date,
                "Lab Name": r.lab_name,
                "Status": r.status
            })
        st.dataframe(df)
    else:
        st.info("No records found for the given filters.")
        
except Exception as e:
    st.error(f"Database query failed: {e}")

st.markdown("---")

# File upload with JSON support
uploaded_file = st.file_uploader("📂 Choose HL7 (.txt/.hl7), CSV (.csv), or JSON (.json) file", 
                                 type=["txt", "hl7", "csv", "json"])
if uploaded_file:
    try:
        content = uploaded_file.read().decode("utf-8")
        name = uploaded_file.name.lower()

        # JSON branch (for LGC eGFR files)
        if name.endswith(".json"):
            st.subheader("JSON Parsing (LGC Format)")
            try:
                # Try to parse as JSON first
                json_data = json.loads(content)
                st.json(json_data)
                
                # For LGC eGFR format, extract lab results
                if "labResults" in json_data:
                    lab_results = json_data["labResults"]
                elif "testResults" in json_data:
                    lab_results = json_data["testResults"]
                else:
                    lab_results = [json_data]  # Single result
                
                # Convert to standard format for normalization
                converted_results = []
                patient_info = json_data.get("patientIdentification", {})
                timestamp = json_data.get("timeStamp", "")
                
                for lab in lab_results:
                    # Convert LGC format to standard format
                    converted = {
                        "patient_id": f"{patient_info.get('lastName', 'UNK')}^{patient_info.get('firstName', 'UNK')}",
                        "test_code": lab.get("coding", [{}])[0].get("code", "UNKNOWN") if lab.get("coding") else "UNKNOWN",
                        "result_value": float(lab.get("quantitativeValue", {}).get("value", 0)) if lab.get("quantitativeValue") else 0,
                        "unit": lab.get("quantitativeValue", {}).get("unit", "") if lab.get("quantitativeValue") else "",
                        "timestamp": timestamp
                    }
                    converted_results.append(converted)
                
                # Process each result
                persisted_ids = []
                for converted in converted_results:
                    try:
                        norm = normalize_result(converted)
                        rec = save_result(norm)
                        if hasattr(rec, 'id') and rec.id != 'ERROR':
                            persisted_ids.append(rec.id)
                    except Exception as e:
                        st.warning(f"Failed to process one JSON record: {e}")
                        continue

                if persisted_ids:
                    st.success(f"Persisted JSON record(s) with ID(s): {persisted_ids}")
                else:
                    st.warning("Records processed but persistence may have failed")

                # Show normalized and FHIR for first result
                if converted_results:
                    first_norm = normalize_result(converted_results[0])
                    st.subheader("Normalized Result (First)")
                    st.json(first_norm)
                    st.subheader("FHIR Output (First)")
                    st.json(build_fhir_output(first_norm))
                    
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON format: {e}")
            except Exception as e:
                st.error(f"Error parsing or saving JSON: {e}")
                logging.error(f"JSON processing error: {e}", exc_info=True)

        # HL7 branch
        elif name.endswith((".hl7", ".txt")):
            st.subheader("HL7 Parsing")
            try:
                # Updated to handle multiple results
                raw_results = parse_hl7(content)  # This now returns a list
                st.json(raw_results)
                
                # Process each result
                persisted_ids = []
                for raw in raw_results:
                    norm = normalize_result(raw)
                    rec = save_result(norm)
                    if hasattr(rec, 'id') and rec.id != 'ERROR':
                        persisted_ids.append(rec.id)

                if persisted_ids:
                    st.success(f"Persisted HL7 record(s) with ID(s): {persisted_ids}")
                else:
                    st.warning("Records processed but persistence may have failed")

                # Show normalized and FHIR for first result
                if raw_results:
                    first_norm = normalize_result(raw_results[0])
                    st.subheader("Normalized Result (First)")
                    st.json(first_norm)
                    st.subheader("FHIR Output (First)")
                    st.json(build_fhir_output(first_norm))
                    
            except Exception as e:
                st.error(f"Error parsing or saving HL7: {e}")
                logging.error(f"HL7 processing error: {e}", exc_info=True)

        # CSV branch
        elif name.endswith(".csv"):
            st.subheader("CSV Parsing")
            try:
                raws = parse_csv(content)
                st.json(raws)

                norms = []
                persisted_ids = []
                
                for r in raws:
                    try:
                        norm = normalize_result(r)
                        norms.append(norm)
                        rec = save_result(norm)
                        if hasattr(rec, 'id') and rec.id != 'ERROR':
                            persisted_ids.append(rec.id)
                    except Exception as e:
                        st.warning(f"Failed to process one CSV record: {e}")
                        continue

                if persisted_ids:
                    st.success(f"Persisted CSV records with IDs: {persisted_ids}")
                else:
                    st.warning("Records processed but persistence may have failed")

                if norms:
                    st.subheader("Normalized Results")
                    st.json(norms)
                    st.subheader("FHIR Outputs")
                    for n in norms:
                        try:
                            st.json(build_fhir_output(n))
                        except Exception as e:
                            st.error(f"FHIR generation failed: {e}")

            except Exception as e:
                st.error(f"Error parsing or saving CSV: {e}")
                logging.error(f"CSV processing error: {e}", exc_info=True)

        else:
            st.warning("Unsupported file type. Upload .hl7/.txt, .csv, or .json files.")
            
    except Exception as e:
        st.error(f"File processing error: {e}")
        logging.error(f"File upload error: {e}", exc_info=True)
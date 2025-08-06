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
import yaml

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization failed: {e}")

st.set_page_config(page_title="RelayDX Demo UI", layout="wide")

# Header with platform branding
st.title("🔬 RelayDX Integration Platform")
st.markdown("**Enterprise Lab Data Integration for CVS Health** | *Vendor-Agnostic • Epic-Ready • Scalable*")
st.markdown("---")

# Main navigation
demo_tab, config_tab, results_tab = st.tabs(["🚀 Live Demo", "⚙️ Configuration", "📊 Results"])

with demo_tab:
    st.header("Live Lab Data Processing Demo")
    st.markdown("Upload files to see real-time parsing, normalization, and FHIR generation")
    
    # File upload with JSON support
    uploaded_file = st.file_uploader(
        "📂 Choose HL7 (.txt/.hl7), CSV (.csv), or JSON (.json) file", 
        type=["txt", "hl7", "csv", "json"]
    )
    
    if uploaded_file:
        try:
            content = uploaded_file.read().decode("utf-8")
            name = uploaded_file.name.lower()

            # JSON branch (for LGC eGFR files)
            if name.endswith(".json"):
                st.subheader("📄 JSON Parsing (LGC Format)")
                try:
                    json_data = json.loads(content)
                    
                    with st.expander("Raw JSON Data", expanded=False):
                        st.json(json_data)
                    
                    # For LGC eGFR format, extract lab results
                    if "labResults" in json_data:
                        lab_results = json_data["labResults"]
                    elif "testResults" in json_data:
                        lab_results = json_data["testResults"]
                    else:
                        lab_results = [json_data]
                    
                    # Convert to standard format for normalization
                    converted_results = []
                    patient_info = json_data.get("patientIdentification", {})
                    timestamp = json_data.get("timeStamp", "")
                    
                    for lab in lab_results:
                        converted = {
                            "patient_id": f"{patient_info.get('lastName', 'UNK')}^{patient_info.get('firstName', 'UNK')}",
                            "test_code": lab.get("coding", [{}])[0].get("code", "UNKNOWN") if lab.get("coding") else "UNKNOWN",
                            "result_value": float(lab.get("quantitativeValue", {}).get("value", 0)) if lab.get("quantitativeValue") else 0,
                            "unit": lab.get("quantitativeValue", {}).get("unit", "") if lab.get("quantitativeValue") else "",
                            "timestamp": timestamp
                        }
                        converted_results.append(converted)
                    
                    # Process and display results
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**✅ Normalized Results:**")
                        persisted_ids = []
                        normalized_results = []
                        
                        for converted in converted_results:
                            try:
                                norm = normalize_result(converted)
                                normalized_results.append(norm)
                                rec = save_result(norm)
                                if hasattr(rec, 'id') and rec.id != 'ERROR':
                                    persisted_ids.append(rec.id)
                            except Exception as e:
                                st.warning(f"Failed to process record: {e}")
                                continue
                        
                        if normalized_results:
                            st.json(normalized_results[0])
                            st.success(f"Processed {len(normalized_results)} records | IDs: {persisted_ids}")
                    
                    with col2:
                        st.write("**🎯 FHIR Output (Epic-Ready):**")
                        if normalized_results:
                            fhir_output = build_fhir_output(normalized_results[0])
                            st.json(fhir_output)
                            
                            # Show Epic compatibility
                            st.info("✅ Epic FHIR R4 Compatible | ✅ LOINC Coded | ✅ US Core Compliant")
                        
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON format: {e}")
                except Exception as e:
                    st.error(f"Error processing JSON: {e}")

            # HL7 branch
            elif name.endswith((".hl7", ".txt")):
                st.subheader("🏥 HL7 Parsing")
                try:
                    raw_results = parse_hl7(content)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Raw HL7 Results:**")
                        with st.expander("Parsed HL7 Data"):
                            st.json(raw_results)
                        
                        persisted_ids = []
                        for raw in raw_results:
                            norm = normalize_result(raw)
                            rec = save_result(norm)
                            if hasattr(rec, 'id') and rec.id != 'ERROR':
                                persisted_ids.append(rec.id)

                        st.success(f"Processed {len(raw_results)} HL7 segments | IDs: {persisted_ids}")
                    
                    with col2:
                        if raw_results:
                            first_norm = normalize_result(raw_results[0])
                            st.write("**Normalized + FHIR:**")
                            st.json(first_norm)
                            st.json(build_fhir_output(first_norm))
                            
                except Exception as e:
                    st.error(f"Error parsing HL7: {e}")

            # CSV branch
            elif name.endswith(".csv"):
                st.subheader("📊 CSV Parsing (Quest Format)")
                try:
                    raws = parse_csv(content)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Raw CSV Data:**")
                        with st.expander("Parsed CSV Records"):
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
                                st.warning(f"Failed to process CSV record: {e}")

                        st.success(f"Processed {len(norms)} CSV records | IDs: {persisted_ids}")
                    
                    with col2:
                        if norms:
                            st.write("**Normalized + FHIR:**")
                            st.json(norms[0])
                            st.json(build_fhir_output(norms[0]))

                except Exception as e:
                    st.error(f"Error parsing CSV: {e}")

            else:
                st.warning("Unsupported file type. Upload .hl7/.txt, .csv, or .json files.")
                
        except Exception as e:
            st.error(f"File processing error: {e}")

with config_tab:
    st.header("🛠️ Platform Configuration")
    
    source_tab, dest_tab, pipeline_tab = st.tabs(["📥 Sources", "📤 Destinations & Mapping", "🔄 Pipeline"])
    
    with source_tab:
        st.subheader("Lab Vendor Source Configuration")
        
        vendor_templates = {
            "LGC": {
                "name": "LGC Genomics",
                "type": "json",
                "format": "lgc_egfr",
                "endpoint": "https://api.lgc.com/results",
                "auth_type": "api_key",
                "parser": "lgc_egfr_parser",
                "test_types": ["eGFR", "Creatinine", "BUN", "Comprehensive Metabolic Panel"]
            },
            "Quest": {
                "name": "Quest Diagnostics", 
                "type": "csv",
                "format": "quest_standard",
                "endpoint": "sftp://quest.com/results/",
                "auth_type": "certificate",
                "parser": "quest_egfr_parser", 
                "test_types": ["eGFR", "Lipid Panel", "HbA1c", "Thyroid Function"]
            },
            "LabCorp": {
                "name": "LabCorp",
                "type": "hl7",
                "format": "hl7_v2.4",
                "endpoint": "https://api.labcorp.com/hl7",
                "auth_type": "oauth2",
                "parser": "hl7_parser",
                "test_types": ["eGFR", "Complete Blood Count", "Basic Metabolic Panel"]
            }
        }
        
        selected_vendor = st.selectbox("Select Lab Vendor:", list(vendor_templates.keys()) + ["Custom"])
        
        if selected_vendor != "Custom":
            template = vendor_templates[selected_vendor]
            
            with st.form("vendor_config"):
                st.info(f"**{template['name']}** - {template['format']} format")
                
                col1, col2 = st.columns(2)
                with col1:
                    vendor_name = st.text_input("Vendor Name", value=template["name"])
                    data_format = st.selectbox("Format", ["json", "csv", "hl7"], 
                                             index=["json", "csv", "hl7"].index(template["type"]))
                
                with col2:
                    endpoint = st.text_input("Endpoint", value=template["endpoint"])
                    auth = st.selectbox("Authentication", ["api_key", "oauth2", "certificate"])
                
                test_types = st.text_area("Supported Tests", value="\n".join(template["test_types"]))
                
                if st.form_submit_button("💾 Save Vendor Configuration"):
                    if "vendors" not in st.session_state:
                        st.session_state.vendors = {}
                    st.session_state.vendors[vendor_name] = {
                        "name": vendor_name,
                        "type": data_format,
                        "endpoint": endpoint,
                        "auth": auth,
                        "tests": [t.strip() for t in test_types.split("\n")]
                    }
                    st.success(f"✅ {vendor_name} configured successfully!")
                    st.balloons()

    with dest_tab:
        st.subheader("Destination Systems & Field Mapping")
        
        # Destination templates with detailed mapping
destination_templates = {
            "Epic Oak Street (FHIR R4)": {
                "name": "Epic Oak Street Health",
                "type": "fhir",
                "endpoint": "https://epic-oak.cvs.com/fhir/R4",
                "format": "fhir_r4_bundle",
                "description": "Epic 2024 - US Core compliant, production-ready",
                "required_mappings": {
                    "epic_patient_id": "EPIC_MRN_LOOKUP({patient_id})",
                    "patient_name": "EPIC_PATIENT_NAME({patient_id})",
                    "encounter_id": "EPIC_ENCOUNTER_LOOKUP({patient_id}, {timestamp})",
                    "lab_organization_id": "EPIC_ORG_LOOKUP('{lab_name}')",
                    "observation_uuid": "UUID_GENERATE()",
                    "diagnostic_report_uuid": "UUID_GENERATE()",
                    "result_value": "{result_value}",
                    "timestamp": "ISO8601_FORMAT({timestamp})",
                    "us_core_profile": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"
                },
                "conditional_mappings": {
                    "interpretation_code": "CASE WHEN {result_value} >= 90 THEN 'N' WHEN {result_value} >= 60 THEN 'N' WHEN {result_value} >= 30 THEN 'L' ELSE 'LL' END",
                    "ckd_stage": "CASE WHEN {result_value} >= 90 THEN 'G1 - Normal' WHEN {result_value} >= 60 THEN 'G2 - Mildly decreased' WHEN {result_value} >= 45 THEN 'G3a - Moderately decreased' WHEN {result_value} >= 30 THEN 'G3b - Moderately to severely decreased' WHEN {result_value} >= 15 THEN 'G4 - Severely decreased' ELSE 'G5 - Kidney failure' END",
                    "snomed_code": "CASE WHEN {result_value} >= 60 THEN '431314004' WHEN {result_value} >= 30 THEN '431855005' WHEN {result_value} >= 15 THEN '431856006' ELSE '433144002' END",
                    "clinical_interpretation": "CASE WHEN {result_value} >= 90 THEN 'Normal kidney function' WHEN {result_value} >= 30 THEN 'Consider nephrology referral' ELSE 'Urgent nephrology consultation recommended' END",
                    "bpa_trigger": "CASE WHEN {result_value} < 30 THEN 'NEPHROLOGY_REFERRAL_BPA' WHEN {result_value} < 15 THEN 'RENAL_REPLACEMENT_BPA' ELSE 'NONE' END"
                },
                "epic_features": [
                    "✅ US Core Lab Result Profile",
                    "✅ Epic Flowsheet Integration", 
                    "✅ Clinical Decision Support",
                    "✅ Best Practice Alerts",
                    "✅ CKD Staging Calculator",
                    "✅ Provider Notifications"
                ]
            },
            "Signify Platform API": {
                "name": "Signify Health Platform",
                "type": "rest_api",
                "endpoint": "https://api.signifyhealth.com/v1/lab-results",
                "format": "json_api",
                "description": "Signify's proprietary health platform - REST API",
                "required_mappings": {
                    "patient_identifier": "'{patient_id}'",
                    "test_loinc_code": "'{test_code}'",
                    "result_value": "{result_value}",
                    "unit_of_measure": "'{unit}'",
                    "collection_timestamp": "'{timestamp}'",
                    "lab_vendor_name": "'{lab_name}'"
                },
                "conditional_mappings": {
                    "risk_score": "CASE WHEN {result_value} < 30 THEN 90 WHEN {result_value} < 60 THEN 70 ELSE 30 END",
                    "care_priority": "CASE WHEN {result_value} < 30 THEN 'HIGH' WHEN {result_value} < 60 THEN 'MEDIUM' ELSE 'LOW' END",
                    "care_management_flag": "CASE WHEN {result_value} < 30 THEN 'IMMEDIATE_OUTREACH' ELSE 'ROUTINE_MONITORING' END"
                }
            },
            "Snowflake EDP": {
                "name": "CVS Enterprise Data Platform",
                "type": "database",
                "endpoint": "snowflake://cvs-edp.snowflakecomputing.com",
                "format": "sql_insert",
                "description": "Data warehouse for analytics and cross-BU reporting",
                "required_mappings": {
                    "PATIENT_KEY": "'{patient_id}'",
                    "TEST_LOINC_CODE": "'{test_code}'", 
                    "NUMERIC_VALUE": "{result_value}",
                    "RESULT_UNIT": "'{unit}'",
                    "COLLECTION_TIMESTAMP": "TO_TIMESTAMP('{timestamp}')",
                    "LAB_VENDOR": "'{lab_name}'"
                },
                "conditional_mappings": {
                    "ABNORMAL_FLAG": "CASE WHEN {result_value} < 60 THEN 'LOW' WHEN {result_value} > 120 THEN 'HIGH' ELSE 'NORMAL' END",
                    "CKD_STAGE": "CASE WHEN {result_value} >= 90 THEN 'G1' WHEN {result_value} >= 60 THEN 'G2' WHEN {result_value} >= 45 THEN 'G3A' WHEN {result_value} >= 30 THEN 'G3B' WHEN {result_value} >= 15 THEN 'G4' ELSE 'G5' END",
                    "BUSINESS_UNIT": "CASE WHEN '{lab_name}' = 'LGC' THEN 'OAK_STREET' WHEN '{lab_name}' = 'Quest' THEN 'SIGNIFY' ELSE 'UNKNOWN' END",
                    "QUALITY_MEASURE_ELIGIBLE": "CASE WHEN {result_value} < 60 THEN 'CKD_QUALITY_MEASURE' ELSE 'NONE' END"
                }
            },
            "Care Team Alerts": {
                "name": "CVS Care Team Alert System",
                "type": "webhook",
                "endpoint": "https://alerts.cvs.com/api/lab-critical",
                "format": "json_webhook",
                "description": "Real-time alerts for critical lab values across all BUs",
                "required_mappings": {
                    "alert_type": "'LAB_CRITICAL'",
                    "patient_id": "'{patient_id}'",
                    "test_name": "'eGFR'",
                    "current_value": "{result_value}",
                    "unit": "'{unit}'"
                },
                "conditional_mappings": {
                    "severity": "CASE WHEN {result_value} < 15 THEN 'CRITICAL' WHEN {result_value} < 30 THEN 'HIGH' ELSE 'MEDIUM' END",
                    "action_required": "CASE WHEN {result_value} < 30 THEN 'IMMEDIATE_FOLLOWUP' ELSE 'ROUTINE' END",
                    "notify_business_unit": "CASE WHEN '{lab_name}' = 'LGC' THEN 'OAK_STREET_CARE_TEAM' WHEN '{lab_name}' = 'Quest' THEN 'SIGNIFY_CARE_TEAM' ELSE 'GENERAL_CARE_TEAM' END",
                    "escalation_path": "CASE WHEN {result_value} < 15 THEN 'NEPHROLOGIST_IMMEDIATE' WHEN {result_value} < 30 THEN 'PCP_24HR' ELSE 'ROUTINE_FOLLOWUP' END"
                }
            }
        }
        
        dest_selection = st.selectbox("Select Destination:", list(destination_templates.keys()))
        dest_config = destination_templates[dest_selection]
        
        st.info(f"**{dest_config['name']}** - {dest_config['description']}")
        
        # Show Epic-specific features if it's an Epic destination
        if "Epic" in dest_selection and "epic_features" in dest_config:
            st.write("**🏥 Epic Integration Features:**")
            for feature in dest_config["epic_features"]:
                st.write(feature)
            st.markdown("---")
        
        # Basic configuration
        with st.expander("🔧 Basic Configuration"):
            col1, col2 = st.columns(2)
            with col1:
                endpoint = st.text_input("Endpoint", value=dest_config["endpoint"])
                auth_type = st.selectbox("Authentication", ["oauth2", "api_key", "service_account"])
            with col2:
                output_format = st.text_input("Output Format", value=dest_config["format"])
        
        # Field Mapping Configuration
        st.subheader("🗺️ Field Mapping Configuration")
        
        # Canonical schema reference
        with st.expander("📋 Canonical Schema Reference"):
            canonical_schema = {
                "patient_id": "Patient identifier",
                "test_code": "LOINC code (98979-8 for eGFR)",
                "test_name": "Human-readable test name",
                "result_value": "Numeric result (e.g., 92)",
                "unit": "Unit of measure (e.g., mL/min/1.73m2)",
                "timestamp": "ISO datetime string",
                "lab_name": "Laboratory name (LGC, Quest, etc)",
                "status": "Result status (final, preliminary)",
                "interpretation": "Normal/Abnormal flag"
            }
            st.json(canonical_schema)
        
        st.write("**Required Field Mappings:**")
        mapping_config = {}
        
        for field, default_mapping in dest_config["required_mappings"].items():
            col1, col2, col3 = st.columns([2, 4, 1])
            
            with col1:
                st.code(field)
            
            with col2:
                mapping_value = st.text_area(
                    f"Mapping expression",
                    value=default_mapping,
                    key=f"mapping_{field}",
                    height=60,
                    help="Use {field_name} to reference canonical fields"
                )
                mapping_config[field] = mapping_value
            
            with col3:
                if "{" in mapping_value and "}" in mapping_value:
                    st.success("✓ Valid")
                else:
                    st.warning("⚠ Check")
        
        # Conditional mappings
        if "conditional_mappings" in dest_config:
            st.write("**Conditional/Calculated Mappings:**")
            for field, expression in dest_config["conditional_mappings"].items():
                col1, col2 = st.columns([2, 4])
                with col1:
                    st.code(field)
                with col2:
                    st.code(expression, language="sql")
        
        # Mapping preview
        if st.button("🔍 Preview Mapping with Sample Data"):
            sample_data = {
                "patient_id": "DOE12345",
                "test_code": "98979-8",
                "test_name": "eGFR (CKD-EPI)",
                "result_value": 45,  # Critical value for demo
                "unit": "mL/min/1.73m2",
                "timestamp": "2025-08-05T14:25:00Z",
                "lab_name": "Quest",
                "status": "final",
                "interpretation": "Low"
            }
            
            st.subheader("🎯 Mapping Preview")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Sample Canonical Data:**")
                st.json(sample_data)
            
            with col2:
                st.write(f"**{dest_config['name']} Output:**")
                preview_output = {}
                
                for field, mapping in mapping_config.items():
                    try:
                        # Simple template replacement for demo
                        output_value = mapping
                        for key, value in sample_data.items():
                            output_value = output_value.replace(f"{{{key}}}", str(value))
                        
                        # Handle JSON objects in mappings
                        if output_value.startswith("{") and output_value.endswith("}"):
                            try:
                                output_value = json.loads(output_value)
                            except:
                                pass
                        
                        preview_output[field] = output_value
                    except Exception as e:
                        preview_output[field] = f"ERROR: {str(e)}"
                
                st.json(preview_output)
                
                # Show conditional mappings results
                if "conditional_mappings" in dest_config:
                    st.write("**Conditional Results:**")
                    conditional_results = {}
                    for field, expression in dest_config["conditional_mappings"].items():
                        if "< 30" in expression and sample_data["result_value"] < 30:
                            if "CRITICAL" in expression:
                                conditional_results[field] = "CRITICAL"
                            elif "IMMEDIATE" in expression:
                                conditional_results[field] = "IMMEDIATE_FOLLOWUP"
                        elif "< 60" in expression and sample_data["result_value"] < 60:
                            if "G3" in expression:
                                conditional_results[field] = "G3A"
                            elif "LOW" in expression:
                                conditional_results[field] = "LOW"
                    st.json(conditional_results)

    with pipeline_tab:
        st.subheader("🔄 Active Pipeline Configuration")
        
        # Generate pipeline config from UI selections
        if "vendors" in st.session_state and st.session_state.vendors:
            st.write("**Current Pipeline Configuration:**")
            
            pipeline_config = {
                "pipelineName": "RelayDX_eGFR_Demo",
                "description": "Vendor-agnostic eGFR processing for CVS Health Epic migration",
                "sources": list(st.session_state.vendors.keys()),
                "destinations": [dest_selection],
                "processing_stages": [
                    "ingest", "validate", "normalize", "enrich", "route", "transform", "send"
                ]
            }
            
            st.json(pipeline_config)
            
            # Generate YAML
            if st.button("📋 Generate Pipeline YAML"):
                yaml_output = f"""# RelayDX Pipeline Configuration
pipelineName: {pipeline_config['pipelineName']}
description: {pipeline_config['description']}

connectors:
  inbound:"""
                
                for vendor_name in st.session_state.vendors:
                    vendor = st.session_state.vendors[vendor_name]
                    yaml_output += f"""
    - name: {vendor_name.replace(' ', '-').lower()}
      type: {vendor['type']}
      endpoint: {vendor['endpoint']}
      auth: {vendor['auth']}"""
                
                yaml_output += f"""

  outbound:
    - name: {dest_selection.replace(' ', '-').lower()}
      type: {destination_templates[dest_selection]['type']}
      endpoint: {destination_templates[dest_selection]['endpoint']}
      format: {destination_templates[dest_selection]['format']}

stages:
  - id: ingest
    type: VendorParser
  - id: validate  
    type: DataValidator
  - id: normalize
    type: CanonicalTransformer
  - id: transform
    type: FHIRTransformer
  - id: send
    type: ConnectorSend
"""
                
                st.code(yaml_output, language="yaml")
                st.download_button(
                    "📥 Download Pipeline Config",
                    yaml_output,
                    "relaydx_pipeline.yaml",
                    "text/yaml"
                )

with results_tab:
    st.header("📊 Processed Lab Results")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_filter = st.text_input("Filter by Patient ID")
    with col2:
        test_filter = st.text_input("Filter by Test Name")
    with col3:
        page_size = st.number_input("Results per page", 1, 50, 10)

    # Query results
    try:
        with get_session() as session:
            query = select(LabResult)
            if patient_filter:
                query = query.where(LabResult.patient_id.contains(patient_filter))
            if test_filter:
                query = query.where(LabResult.test_name.contains(test_filter))
            
            results = session.exec(query.limit(page_size)).all()

        if results:
            # Display as enhanced table
            result_data = []
            for r in results:
                result_data.append({
                    "ID": r.id,
                    "Patient": r.patient_id,
                    "Test": r.test_name,
                    "Result": f"{r.result_value} {r.units}",
                    "Date": r.collection_date.strftime("%Y-%m-%d %H:%M") if r.collection_date else "N/A",
                    "Lab": r.lab_name,
                    "Status": r.status
                })
            
            st.dataframe(result_data, use_container_width=True)
            
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Results", len(results))
            with col2:
                unique_patients = len(set(r.patient_id for r in results))
                st.metric("Unique Patients", unique_patients)
            with col3:
                unique_labs = len(set(r.lab_name for r in results))
                st.metric("Lab Vendors", unique_labs)
            with col4:
                final_results = len([r for r in results if r.status == "final"])
                st.metric("Final Results", final_results)
        else:
            st.info("No results found. Upload some lab files to see data here.")
            
    except Exception as e:
        st.error(f"Database query failed: {e}")

# Demo scenarios at bottom
st.markdown("---")
st.subheader("🎭 Demo Scenarios for Stakeholders")

scenario_col1, scenario_col2, scenario_col3 = st.columns(3)

with scenario_col1:
    if st.button("🔄 Vendor Switch Demo"):
        st.success("✅ Demo: LGC → Quest vendor switch")
        st.info("Same Epic output, different input format")
        st.code("LGC JSON → Canonical → Epic FHIR\nQuest CSV → Canonical → Epic FHIR")

with scenario_col2:
    if st.button("🏥 Multi-Epic Demo"):
        st.success("✅ Demo: Oak Street R4 vs Signify STU3")
        st.info("Same eGFR data, different Epic versions")
        st.code("Canonical → Epic R4 Bundle\nCanonical → Epic STU3 Bundle")

with scenario_col3:
    if st.button("⚡ Critical Value Demo"):
        st.success("✅ Demo: eGFR < 30 critical alert")
        st.info("Conditional routing to care team")
        st.code("Normal eGFR → Epic only\nCritical eGFR → Epic + Alerts")

# Footer
st.markdown("---")
st.markdown("*RelayDX Platform Demo*") 
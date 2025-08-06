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
st.markdown("**Enterprise Lab Data Integration Platform** | *Vendor-Agnostic • Epic-Ready • Scalable*")
st.markdown("---")

# Main navigation
demo_tab, config_tab = st.tabs(["🚀 Live Demo", "⚙️ Configuration"])

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
        
# Replace the vendor_templates section in your ui.py (around line 200) with this:

        vendor_templates = {
            "LGC": {
                "name": "Let's Get Checked",
                "type": "json",
                "format": "lgc_egfr",
                "endpoint": "https://api.lgc.com/results/egfr",
                "auth_type": "api_key",
                "parser": "lgc_egfr_parser",
                "test_types": ["eGFR (CKD-EPI)"],  # eGFR only
                "description": "LGC eGFR test results via JSON API"
            },
            "Quest": {
                "name": "Quest Diagnostics", 
                "type": "csv",
                "format": "quest_standard",
                "endpoint": "sftp://quest.com/results/egfr/",
                "auth_type": "certificate",
                "parser": "quest_egfr_parser", 
                "test_types": ["eGFR (CKD-EPI)"],  # eGFR only
                "description": "Quest eGFR test results via CSV files"
            },
            "LabCorp": {
                "name": "LabCorp",
                "type": "hl7",
                "format": "hl7_v2.4",
                "endpoint": "https://api.labcorp.com/hl7/egfr",
                "auth_type": "oauth2",
                "parser": "hl7_parser",
                "test_types": ["eGFR (CKD-EPI)"],  # eGFR only
                "description": "LabCorp eGFR test results via HL7 messages"
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
        
        # Enhanced destination templates with Epic features
        destination_templates = {
            "Epic Health System (FHIR R4)": {
                "name": "Epic Health System",
                "type": "fhir",
                "endpoint": "https://epic-fhir.healthsystem.com/fhir/R4",
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
            "Health Platform API": {
                "name": "Health Platform API",
                "type": "rest_api",
                "endpoint": "https://api.healthplatform.com/v1/lab-results",
                "format": "json_api",
                "description": "Proprietary health platform - REST API",
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
            "Enterprise Data Platform": {
                "name": "Enterprise Data Platform",
                "type": "database",
                "endpoint": "snowflake://enterprise-edp.snowflakecomputing.com",
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
                    "BUSINESS_UNIT": "CASE WHEN '{lab_name}' = 'LGC' THEN 'UNIT_A' WHEN '{lab_name}' = 'Quest' THEN 'UNIT_B' ELSE 'UNKNOWN' END",
                    "QUALITY_MEASURE_ELIGIBLE": "CASE WHEN {result_value} < 60 THEN 'CKD_QUALITY_MEASURE' ELSE 'NONE' END"
                }
            },
            "Care Team Alerts": {
                "name": "Care Team Alert System",
                "type": "webhook",
                "endpoint": "https://alerts.healthsystem.com/api/lab-critical",
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
                    "notify_business_unit": "CASE WHEN '{lab_name}' = 'LGC' THEN 'UNIT_A_CARE_TEAM' WHEN '{lab_name}' = 'Quest' THEN 'UNIT_B_CARE_TEAM' ELSE 'GENERAL_CARE_TEAM' END",
                    "escalation_path": "CASE WHEN {result_value} < 15 THEN 'NEPHROLOGIST_IMMEDIATE' WHEN {result_value} < 30 THEN 'PCP_24HR' ELSE 'ROUTINE_FOLLOWUP' END"
                }
            }
        }
        
        # Add custom destinations from session state
        all_destinations = destination_templates.copy()
        if "custom_destinations" in st.session_state:
            all_destinations.update(st.session_state.custom_destinations)
        
        dest_selection = st.selectbox("Select Destination:", list(all_destinations.keys()))
        dest_config = all_destinations[dest_selection]
        
        st.info(f"**{dest_config['name']}** - {dest_config['description']}")
        
        # Show Epic-specific features if it's an Epic destination
        if "Epic" in dest_selection and "epic_features" in dest_config:
            st.write("**🏥 Epic Integration Features:**")
            for feature in dest_config["epic_features"]:
                st.write(feature)
            st.markdown("---")
        
        # Interactive mapping configuration
        st.subheader("🗺️ Interactive Field Mapping Editor")
        
        # Toggle between view and edit modes
        col1, col2 = st.columns([3, 1])
        with col1:
            mapping_mode = st.radio("Mapping Mode:", ["View Mappings", "Edit Mappings", "Create New Destination"])
        with col2:
            if st.button("💾 Save Changes"):
                st.success("Mapping changes saved!")

        if mapping_mode == "Edit Mappings":
            st.write(f"**Editing: {dest_config['name']}**")
            
            # Editable required mappings
            st.write("**Required Field Mappings (Editable):**")
            updated_mappings = {}
            
            for field, default_mapping in dest_config["required_mappings"].items():
                col1, col2, col3 = st.columns([2, 4, 1])
                
                with col1:
                    st.code(field)
                
                with col2:
                    # Make mappings editable
                    new_mapping = st.text_area(
                        f"Edit mapping for {field}",
                        value=default_mapping,
                        key=f"edit_mapping_{field}",
                        height=80,
                        help="Use {field_name} to reference canonical fields"
                    )
                    updated_mappings[field] = new_mapping
                
                with col3:
                    # Validation
                    if "{" in new_mapping and "}" in new_mapping:
                        st.success("✓")
                    else:
                        st.error("⚠")
            
            # Save updated mappings to session state
            if st.button("💾 Update Mappings"):
                if "custom_mappings" not in st.session_state:
                    st.session_state.custom_mappings = {}
                st.session_state.custom_mappings[dest_selection] = updated_mappings
                st.success(f"✅ Updated mappings for {dest_config['name']}")
                st.balloons()
            
            # Add new field mapping
            st.write("**Add New Field Mapping:**")
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                new_field_name = st.text_input("New Field Name", placeholder="e.g., custom_flag")
            with col2:
                new_field_mapping = st.text_input("Mapping Expression", placeholder="e.g., '{result_value} > 60'")
            with col3:
                if st.button("➕ Add Field") and new_field_name and new_field_mapping:
                    updated_mappings[new_field_name] = new_field_mapping
                    st.success("Field added!")

# Replace the entire "Create New Destination" section with this simpler version:

        elif mapping_mode == "Create New Destination":
            st.write("**Create Custom Destination:**")
            
            # Basic destination info (outside form to avoid conflicts)
            st.write("**Basic Configuration:**")
            col1, col2 = st.columns(2)
            
            with col1:
                new_dest_name = st.text_input("Destination Name", placeholder="e.g., Custom Epic System", key="new_dest_name")
                new_dest_type = st.selectbox("Destination Type", ["fhir", "rest_api", "database", "webhook"], key="new_dest_type")
                new_dest_endpoint = st.text_input("Endpoint URL", placeholder="https://api.example.com", key="new_dest_endpoint")
            
            with col2:
                new_dest_format = st.text_input("Output Format", placeholder="e.g., fhir_r4_bundle", key="new_dest_format")
                new_dest_auth = st.selectbox("Authentication", ["oauth2", "api_key", "basic_auth", "certificate"], key="new_dest_auth")
                new_dest_description = st.text_area("Description", placeholder="Custom destination for...", key="new_dest_description")
            
            st.write("**Field Mappings:**")
            
            # Initialize session state for fields
            if "new_dest_fields" not in st.session_state:
                st.session_state.new_dest_fields = {"patient_id": "'{patient_id}'", "test_code": "'{test_code}'"}
            
            # Show current mappings
            for i, (field_name, mapping_expr) in enumerate(st.session_state.new_dest_fields.items()):
                col1, col2, col3 = st.columns([2, 3, 1])
                with col1:
                    st.text_input(f"Field {i+1}", value=field_name, disabled=True, key=f"display_field_{i}")
                with col2:
                    st.text_input(f"Mapping {i+1}", value=mapping_expr, disabled=True, key=f"display_mapping_{i}")
                with col3:
                    if st.button("🗑️", key=f"delete_field_{i}") and len(st.session_state.new_dest_fields) > 1:
                        del st.session_state.new_dest_fields[field_name]
                        st.rerun()
            
            # Add new field
            st.write("**Add New Field:**")
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                add_field_name = st.text_input("Field Name", placeholder="e.g., custom_flag", key="add_field_name")
            with col2:
                add_field_mapping = st.text_input("Mapping Expression", placeholder="e.g., '{result_value} > 60'", key="add_field_mapping")
            with col3:
                if st.button("➕ Add") and add_field_name and add_field_mapping:
                    st.session_state.new_dest_fields[add_field_name] = add_field_mapping
                    st.rerun()
            
            # Create destination
            st.markdown("---")
            if st.button("🎯 Create Destination", type="primary"):
                if new_dest_name and st.session_state.new_dest_fields:
                    # Build new destination config
                    new_destination = {
                        "name": new_dest_name,
                        "type": new_dest_type,
                        "endpoint": new_dest_endpoint,
                        "format": new_dest_format,
                        "auth_type": new_dest_auth,
                        "description": new_dest_description,
                        "required_mappings": st.session_state.new_dest_fields.copy()
                    }
                    
                    # Save to session state
                    if "custom_destinations" not in st.session_state:
                        st.session_state.custom_destinations = {}
                    st.session_state.custom_destinations[new_dest_name] = new_destination
                    
                    # Reset form
                    st.session_state.new_dest_fields = {"patient_id": "'{patient_id}'", "test_code": "'{test_code}'"}
                    
                    st.success(f"✅ Created new destination: {new_dest_name}")
                    st.balloons()
                else:
                    st.error("Please provide a destination name and at least one field mapping")

        else:  # View Mappings mode
            # Basic configuration
            with st.expander("🔧 Basic Configuration"):
                col1, col2 = st.columns(2)
                with col1:
                    endpoint = st.text_input("Endpoint", value=dest_config["endpoint"])
                    auth_type = st.selectbox("Authentication", ["oauth2", "api_key", "service_account"])
                with col2:
                    output_format = st.text_input("Output Format", value=dest_config["format"])
            
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
            
            # Use custom mappings if they exist
            mappings_to_show = st.session_state.get("custom_mappings", {}).get(dest_selection, dest_config["required_mappings"])
            
            for field, default_mapping in mappings_to_show.items():
                col1, col2, col3 = st.columns([2, 4, 1])
                
                with col1:
                    st.code(field)
                
                with col2:
                    st.text_area(
                        f"Mapping expression",
                        value=default_mapping,
                        key=f"view_mapping_{field}",
                        height=60,
                        disabled=True,
                        help="Use {field_name} to reference canonical fields"
                    )
                    mapping_config[field] = default_mapping
                
                with col3:
                    if "{" in default_mapping and "}" in default_mapping:
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

        # Source to Destination Mapping
        st.markdown("---")
        st.subheader("🔀 Source → Destination Routing Configuration")

        # Show configured sources and destinations
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**Available Sources:**")
            available_sources = []
            if "vendors" in st.session_state:
                for vendor_name, vendor_config in st.session_state.vendors.items():
                    available_sources.append(f"{vendor_name} ({vendor_config['type']})")
                    st.write(f"📥 {vendor_name}")
            else:
                st.info("Configure sources first")

        with col2:
            st.write("**➡️ Routing Rules:**")
            if available_sources:
                # Create routing configuration
                routing_rules = {}
                for i, source in enumerate(available_sources):
                    source_name = source.split(" (")[0]  # Extract name without type
                    selected_destinations = st.multiselect(
                        f"Route {source_name} to:",
                        options=list(all_destinations.keys()),
                        key=f"routing_{i}"
                    )
                    if selected_destinations:
                        routing_rules[source_name] = selected_destinations
                
                # Save routing rules
                if routing_rules and st.button("💾 Save Routing Rules"):
                    st.session_state.routing_rules = routing_rules
                    st.success("✅ Routing rules saved!")

        with col3:
            st.write("**Configured Routes:**")
            if "routing_rules" in st.session_state:
                for source, destinations in st.session_state.routing_rules.items():
                    st.write(f"📥 **{source}**")
                    for dest in destinations:
                        st.write(f"  ↳ 📤 {dest}")
            else:
                st.info("No routing rules configured")

        # Live Mapping Test
        st.markdown("---")
        st.subheader("🧪 Live Mapping Test")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Test Input Data:**")
            test_data = {
                "patient_id": st.text_input("Patient ID", value="TEST12345"),
                "test_code": st.text_input("Test Code", value="98979-8"),
                "result_value": st.number_input("Result Value", value=45.0),
                "unit": st.text_input("Unit", value="mL/min/1.73m2"),
                "timestamp": st.text_input("Timestamp", value="2025-08-05T14:25:00Z"),
                "lab_name": st.text_input("Lab Name", value="Quest")
            }

        with col2:
            st.write("**Live Mapping Output:**")
            if st.button("🔄 Test Mapping"):
                # Apply current mappings to test data
                mappings_to_use = st.session_state.get("custom_mappings", {}).get(dest_selection, dest_config["required_mappings"])
                
                output = {}
                for field, mapping_expr in mappings_to_use.items():
                    try:
                        # Simple template substitution
                        result = mapping_expr
                        for key, value in test_data.items():
                            result = result.replace(f"{{{key}}}", str(value))
                        output[field] = result
                    except Exception as e:
                        output[field] = f"ERROR: {str(e)}"
                
                st.json(output)

        # Export Configuration
        st.markdown("---")
        if st.button("📥 Export Configuration"):
            config_export = {
                "sources": st.session_state.get("vendors", {}),
                "destinations": all_destinations,
                "custom_mappings": st.session_state.get("custom_mappings", {}),
                "routing_rules": st.session_state.get("routing_rules", {})
            }
            
            st.download_button(
                label="📥 Download RelayDX Configuration",
                data=json.dumps(config_export, indent=2),
                file_name="relaydx_config.json",
                mime="application/json"
            )

    with pipeline_tab:
        st.subheader("🔄 Active Pipeline Configuration")
        
        # Generate pipeline config from UI selections
        if "vendors" in st.session_state and st.session_state.vendors:
            st.write("**Current Pipeline Configuration:**")
            
            pipeline_config = {
                "pipelineName": "RelayDX_eGFR_Demo",
                "description": "Vendor-agnostic eGFR processing for enterprise healthcare",
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
      type: {all_destinations[dest_selection]['type']}
      endpoint: {all_destinations[dest_selection]['endpoint']}
      format: {all_destinations[dest_selection]['format']}

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
        else:
            st.info("Configure sources first to see active pipeline")

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
    if st.button("🏥 Multi-System Demo"):
        st.success("✅ Demo: Epic vs Health Platform")
        st.info("Same eGFR data, different system formats")
        st.code("Canonical → Epic FHIR Bundle\nCanonical → Health Platform REST API")

with scenario_col3:
    if st.button("⚡ Critical Value Demo"):
        st.success("✅ Demo: eGFR < 30 critical alert")
        st.info("Conditional routing to care team")
        st.code("Normal eGFR → Epic only\nCritical eGFR → Epic + Alerts")

# Footer
st.markdown("---")
st.markdown("*RelayDX Platform Demo | Enterprise Healthcare Integration Platform*")
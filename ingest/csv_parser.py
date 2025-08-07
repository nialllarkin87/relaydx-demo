# Replace your ingest/csv_parser.py with this enhanced version:

import pandas as pd
from io import StringIO
from typing import List, Dict

def parse_csv(content: str) -> List[Dict]:
    """
    Enhanced CSV parser that extracts patient names and other details
    """
    try:
        df = pd.read_csv(StringIO(content))
        records = []
        for _, row in df.iterrows():
            
            # Extract patient information
            patient_id = None
            patient_name = ""
            
            # Try different patient ID column names
            if "Patient_ID" in row:
                patient_id = row["Patient_ID"]
            elif "MRN" in row:
                patient_id = row["MRN"]
            elif "PATIENT_ID" in row:
                patient_id = row["PATIENT_ID"]
            else:
                patient_id = "UNKNOWN"
            
            # Build patient name from separate fields (Quest format)
            if "PATIENT_LAST" in row and "PATIENT_FIRST" in row:
                last_name = row["PATIENT_LAST"] or "Unknown"
                first_name = row["PATIENT_FIRST"] or "Unknown"
                patient_name = f"{last_name}^{first_name}^{patient_id}"
            elif "Patient_Last" in row and "Patient_First" in row:
                last_name = row["Patient_Last"] or "Unknown"
                first_name = row["Patient_First"] or "Unknown"
                patient_name = f"{last_name}^{first_name}^{patient_id}"
            else:
                # Fallback to just patient ID
                patient_name = str(patient_id)
            
            # Extract test code
            test_code = None
            if "Test_LOINC_Code" in row:
                test_code = row["Test_LOINC_Code"]
            elif "TEST_CODE" in row:
                test_code = row["TEST_CODE"]
            elif "Test_Code" in row:
                test_code = row["Test_Code"]
            else:
                test_code = "98979-8"  # Default to eGFR LOINC
            
            # Extract result value
            result_value = 0
            if "Result" in row:
                try:
                    result_value = float(row["Result"])
                except (ValueError, TypeError):
                    result_value = 0
            elif "NUMERIC_RESULT" in row:
                try:
                    result_value = float(row["NUMERIC_RESULT"])
                except (ValueError, TypeError):
                    result_value = 0
            elif "Result_Value" in row:
                try:
                    result_value = float(row["Result_Value"])
                except (ValueError, TypeError):
                    result_value = 0
            
            # Extract unit
            unit = ""
            if "Units" in row:
                unit = row["Units"]
            elif "RESULT_UNITS" in row:
                unit = row["RESULT_UNITS"]
            elif "Unit" in row:
                unit = row["Unit"]
            else:
                unit = "mL/min/1.73m2"  # Default for eGFR
            
            # Extract timestamp
            timestamp = ""
            if "Result_Date" in row:
                timestamp = row["Result_Date"]
            elif "COLLECTION_DATETIME" in row:
                timestamp = row["COLLECTION_DATETIME"]
            elif "Collection_Date" in row:
                timestamp = row["Collection_Date"]
            else:
                timestamp = "2025-08-06T12:00:00Z"  # Default timestamp
            
            # Build the record
            record = {
                "patient_id": patient_name,  # Use full name instead of just ID
                "test_code": test_code,
                "result_value": result_value,
                "unit": unit,
                "timestamp": timestamp
            }
            
            records.append(record)
        
        return records
        
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {e}")

def parse_csv_simple(content: str) -> List[Dict]:
    """
    Fallback simple CSV parser
    """
    try:
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return []
        
        headers = lines[0].split(',')
        records = []
        
        for line in lines[1:]:
            values = line.split(',')
            if len(values) >= len(headers):
                record = dict(zip(headers, values))
                
                # Try to extract basic info
                patient_id = record.get('MRN', 'UNKNOWN')
                last_name = record.get('PATIENT_LAST', 'Unknown')
                first_name = record.get('PATIENT_FIRST', 'Unknown')
                
                records.append({
                    "patient_id": f"{last_name}^{first_name}^{patient_id}",
                    "test_code": record.get('TEST_CODE', '98979-8'),
                    "result_value": float(record.get('NUMERIC_RESULT', 0)),
                    "unit": record.get('RESULT_UNITS', 'mL/min/1.73m2'),
                    "timestamp": record.get('COLLECTION_DATETIME', '2025-08-06T12:00:00Z')
                })
        
        return records
        
    except Exception as e:
        return []
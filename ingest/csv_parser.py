# ingest/csv_parser.py
import pandas as pd
from io import StringIO  # Use io.StringIO instead of pandas.compat.StringIO
from typing import List, Dict

def parse_csv(content: str) -> List[Dict]:
    """
    content: full CSV text
    returns: list of raw dicts matching your canonical model keys
    """
    try:
        df = pd.read_csv(StringIO(content))  # Use io.StringIO
        records = []
        for _, row in df.iterrows():
            # Handle different CSV column formats
            record = {}
            
            # Try different patient ID column names
            if "Patient_ID" in row:
                record["patient_id"] = row["Patient_ID"]
            elif "MRN" in row:
                record["patient_id"] = row["MRN"]
            elif "PATIENT_ID" in row:
                record["patient_id"] = row["PATIENT_ID"]
            else:
                record["patient_id"] = "UNKNOWN"
            
            # Try different test code column names
            if "Test_LOINC_Code" in row:
                record["test_code"] = row["Test_LOINC_Code"]
            elif "TEST_CODE" in row:
                record["test_code"] = row["TEST_CODE"]
            elif "Test_Code" in row:
                record["test_code"] = row["Test_Code"]
            else:
                record["test_code"] = "UNKNOWN"
            
            # Try different result value column names
            if "Result" in row:
                record["result_value"] = row["Result"]
            elif "NUMERIC_RESULT" in row:
                record["result_value"] = row["NUMERIC_RESULT"]
            elif "Result_Value" in row:
                record["result_value"] = row["Result_Value"]
            else:
                record["result_value"] = 0
            
            # Try different unit column names
            if "Units" in row:
                record["unit"] = row["Units"]
            elif "RESULT_UNITS" in row:
                record["unit"] = row["RESULT_UNITS"]
            elif "Unit" in row:
                record["unit"] = row["Unit"]
            else:
                record["unit"] = ""
            
            # Try different timestamp column names
            if "Result_Date" in row:
                record["timestamp"] = row["Result_Date"]
            elif "COLLECTION_DATETIME" in row:
                record["timestamp"] = row["COLLECTION_DATETIME"]
            elif "Collection_Date" in row:
                record["timestamp"] = row["Collection_Date"]
            else:
                record["timestamp"] = ""
            
            records.append(record)
        
        return records
        
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {e}")
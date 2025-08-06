# ingest/quest_egfr_parser.py
import csv
from io import StringIO
from typing import List, Dict

def parse_quest_egfr(content: str) -> List[Dict]:
    """
    Parse Quest's CSV format for eGFR results
    Returns list of canonical format dicts
    """
    try:
        csv_reader = csv.DictReader(StringIO(content))
        results = []
        
        for row in csv_reader:
            test_code = row.get("TEST_CODE", "")
            test_name = row.get("TEST_NAME", "").upper()
            
            # Check if this is an eGFR test
            if (test_code in ["EGFR", "33914-3", "98979-8"] or 
                "EGFR" in test_name or 
                "GLOMERULAR" in test_name):
                
                try:
                    # Extract numeric result
                    numeric_result = row.get("NUMERIC_RESULT", "0")
                    if not numeric_result or numeric_result == "":
                        continue
                    
                    result_value = float(numeric_result)
                    
                    canonical_result = {
                        "patient_id": row.get("MRN", "UNKNOWN"),
                        "test_code": "98979-8",  # Standardized LOINC
                        "test_name": "eGFR (CKD-EPI)",
                        "result_value": result_value,
                        "unit": row.get("RESULT_UNITS", "mL/min/1.73m2"),
                        "reference_range": row.get("REFERENCE_RANGE", "≥90"),
                        "timestamp": row.get("COLLECTION_DATETIME", ""),
                        "lab_name": "Quest",
                        "status": "final",
                        "interpretation": row.get("ABNORMAL_FLAG", "Normal")
                    }
                    results.append(canonical_result)
                    
                except (ValueError, TypeError) as e:
                    # Skip invalid numeric results but log warning
                    import logging
                    logging.getLogger(__name__).warning(f"Invalid eGFR value in Quest data: {e}")
                    continue
        
        if not results:
            raise ValueError("No eGFR results found in Quest CSV data")
            
        return results
        
    except Exception as e:
        raise ValueError(f"Failed to parse Quest CSV: {e}")
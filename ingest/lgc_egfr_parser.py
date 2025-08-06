# ingest/lgc_egfr_parser.py
import json
from typing import List, Dict

def parse_lgc_egfr(content: str) -> List[Dict]:
    """
    Parse LGC's JSON format for eGFR results
    Returns list of canonical format dicts
    """
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    
    results = []
    patient = data.get("patientIdentification", {})
    timestamp = data.get("timeStamp", "")
    
    # Handle both labResults and testResults arrays
    test_results = data.get("labResults", data.get("testResults", []))
    
    if not test_results:
        raise ValueError("No test results found in LGC data")
    
    # Find eGFR result in test results array
    for test in test_results:
        biomarker_name = test.get("biomarkerName", "").upper()
        test_code = test.get("testCode", "")
        
        # Check if this is an eGFR test
        if ("EGFR" in biomarker_name or 
            "GLOMERULAR" in biomarker_name or 
            test_code == "EGFR001"):
            
            try:
                quant_value = test.get("quantitativeValue", {})
                coding = test.get("coding", [{}])
                
                # Build patient identifier
                patient_id = f"{patient.get('lastName', 'UNK')}^{patient.get('firstName', 'UNK')}^{patient.get('dob', 'UNK')}"
                
                canonical_result = {
                    "patient_id": patient_id,
                    "test_code": coding[0].get("code", "98979-8") if coding else "98979-8",
                    "test_name": "eGFR (CKD-EPI)",
                    "result_value": float(quant_value.get("value", 0)),
                    "unit": quant_value.get("unit", "mL/min/1.73m2"),
                    "reference_range": f"{quant_value.get('lowerBound', 90)}-{quant_value.get('upperBound', 120)}",
                    "timestamp": timestamp,
                    "lab_name": "LGC",
                    "status": "final",
                    "interpretation": test.get("descriptor", "Normal")
                }
                results.append(canonical_result)
                
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid eGFR data format: {e}")
    
    if not results:
        raise ValueError("No eGFR results found in LGC data")
    
    return results
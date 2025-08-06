# ingest/hl7_parser.py
import hl7
from typing import Dict, List

def parse_hl7(content: str) -> Dict:
    """
    Very basic HL7 ORU^R01 parser for one observation
    """
    msg = hl7.parse(content)
    pid = msg.segment('PID')
    obr = msg.segment('OBR')
    obx = msg.segment('OBX')
    return {
        "patient_id": pid[3][0],                 # e.g. MRN
        "test_code":  obx[3][0],                 # LOINC
        "result_value": float(obx[5][0]),
        "unit": obx[6][0],
        "timestamp": obr[7][0],                  # Observation Date/Time
    }


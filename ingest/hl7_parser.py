# ingest/hl7_parser.py
import hl7
from typing import Dict, List

def parse_hl7(content: str) -> List[Dict]:
    """
    Enhanced HL7 ORU^R01 parser supporting multiple OBX segments
    Returns list of results for multiple observations
    """
    try:
        msg = hl7.parse(content)
        pid = msg.segment('PID')
        
        if not pid:
            raise ValueError("No PID segment found in HL7 message")
        
        results = []
        obx_segments = msg.segments('OBX')
        
        if not obx_segments:
            raise ValueError("No OBX segments found in HL7 message")
        
        for obx in obx_segments:
            try:
                # Extract patient ID from PID segment
                patient_id = str(pid[3][0]) if pid[3] and pid[3][0] else "UNKNOWN"
                
                # Extract test code from OBX segment
                test_code = str(obx[3][0][0]) if obx[3] and len(obx[3][0]) > 0 else "UNKNOWN"
                
                # Extract result value, handle both numeric and text results
                result_value = obx[5][0] if obx[5] and obx[5][0] else None
                if result_value:
                    try:
                        result_value = float(result_value)
                    except (ValueError, TypeError):
                        # Keep as string if not numeric
                        result_value = str(result_value)
                
                # Extract unit
                unit = str(obx[6][0]) if obx[6] and obx[6][0] else ""
                
                # Extract timestamp - try multiple possible locations
                timestamp = None
                if obx[14] and obx[14][0]:  # OBX timestamp
                    timestamp = str(obx[14][0])
                else:
                    # Try to get from OBR segment
                    obr_segments = msg.segments('OBR')
                    if obr_segments and obr_segments[0][7] and obr_segments[0][7][0]:
                        timestamp = str(obr_segments[0][7][0])
                
                result = {
                    "patient_id": patient_id,
                    "test_code": test_code,
                    "result_value": result_value,
                    "unit": unit,
                    "timestamp": timestamp or "",
                }
                results.append(result)
                
            except Exception as e:
                # Log the error but continue processing other OBX segments
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse OBX segment: {e}")
                continue
        
        if not results:
            raise ValueError("No valid results extracted from HL7 message")
            
        return results
        
    except Exception as e:
        raise ValueError(f"Failed to parse HL7 message: {e}")

def parse_hl7_single(content: str) -> Dict:
    """
    Legacy single-result parser for backward compatibility
    Returns first result only
    """
    results = parse_hl7(content)
    return results[0] if results else {}
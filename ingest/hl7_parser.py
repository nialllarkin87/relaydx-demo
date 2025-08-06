
import hl7
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

def parse_hl7(content: str) -> List[Dict]:
    """
    Enhanced HL7 ORU^R01 parser supporting multiple messages and better error handling
    """
    try:
        # Split content by message separators (MSH segments)
        messages = []
        lines = content.strip().split('\n')
        current_message = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('MSH'):
                # Start of new message
                if current_message:
                    messages.append('\n'.join(current_message))
                current_message = [line]
            else:
                current_message.append(line)
        
        # Don't forget the last message
        if current_message:
            messages.append('\n'.join(current_message))
        
        if not messages:
            raise ValueError("No HL7 messages found in content")
        
        logger.info(f"Found {len(messages)} HL7 messages")
        
        all_results = []
        
        for i, message_content in enumerate(messages):
            try:
                # Parse individual HL7 message
                msg = hl7.parse(message_content)
                
                # Find PID segment
                pid_segment = None
                for segment in msg.segments():
                    if segment[0][0] == 'PID':
                        pid_segment = segment
                        break
                
                if not pid_segment:
                    logger.warning(f"No PID segment found in message {i+1}")
                    continue
                
                # Find OBX segments
                obx_segments = []
                for segment in msg.segments():
                    if segment[0][0] == 'OBX':
                        obx_segments.append(segment)
                
                if not obx_segments:
                    logger.warning(f"No OBX segments found in message {i+1}")
                    continue
                
                # Process each OBX segment
                for obx in obx_segments:
                    try:
                        # Extract patient ID from PID segment
                        patient_id = str(pid_segment[3][0]) if len(pid_segment) > 3 and pid_segment[3] else f"UNKNOWN_{i}"
                        
                        # Extract test info from OBX segment
                        test_info = obx[3][0] if len(obx) > 3 and obx[3] else "UNKNOWN^UNKNOWN"
                        test_parts = str(test_info).split('^')
                        test_code = test_parts[0] if len(test_parts) > 0 else "UNKNOWN"
                        
                        # Extract result value
                        result_value = obx[5][0] if len(obx) > 5 and obx[5] else None
                        if result_value:
                            try:
                                result_value = float(result_value)
                            except (ValueError, TypeError):
                                result_value = str(result_value)
                        
                        # Extract unit
                        unit = str(obx[6][0]) if len(obx) > 6 and obx[6] else ""
                        
                        # Extract timestamp from OBR or use current
                        timestamp = ""
                        for segment in msg.segments():
                            if segment[0][0] == 'OBR' and len(segment) > 7 and segment[7]:
                                timestamp = str(segment[7][0])
                                break
                        
                        if not timestamp:
                            from datetime import datetime
                            timestamp = datetime.now().isoformat()
                        
                        result = {
                            "patient_id": patient_id,
                            "test_code": test_code,
                            "result_value": result_value,
                            "unit": unit,
                            "timestamp": timestamp,
                        }
                        
                        all_results.append(result)
                        logger.info(f"Parsed HL7 result: Patient {patient_id}, Test {test_code}, Value {result_value}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to parse OBX segment in message {i+1}: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to parse HL7 message {i+1}: {e}")
                continue
        
        if not all_results:
            raise ValueError("No valid results extracted from HL7 content. Check HL7 message format.")
        
        logger.info(f"Successfully parsed {len(all_results)} HL7 results")
        return all_results
        
    except Exception as e:
        logger.error(f"HL7 parsing failed: {e}")
        raise ValueError(f"Failed to parse HL7 message: {str(e)}")

def parse_hl7_single(content: str) -> Dict:
    """
    Legacy single-result parser for backward compatibility
    Returns first result only
    """
    results = parse_hl7(content)
    return results[0] if results else {}
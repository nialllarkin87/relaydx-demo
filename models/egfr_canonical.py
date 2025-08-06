# models/egfr_canonical.py
from pydantic import BaseModel, validator
from typing import Optional, Literal
from datetime import datetime

class CanonicalEGFRResult(BaseModel):
    """Canonical eGFR result format - vendor agnostic"""
    patient_id: str
    test_code: str = "98979-8"  # Standard LOINC for eGFR
    test_name: str = "eGFR (CKD-EPI)"
    result_value: float
    unit: str = "mL/min/1.73m2"
    reference_range: str
    timestamp: str  # ISO datetime string
    lab_name: str
    status: str = "final"
    interpretation: Optional[str] = None
    
    @validator('patient_id')
    def validate_patient_id(cls, v):
        if not v or v.strip() == "" or v == "UNKNOWN":
            raise ValueError('Patient ID cannot be empty or unknown')
        return v.strip()
    
    @validator('result_value')
    def validate_egfr_range(cls, v):
        if v < 0 or v > 200:  # Physiologically reasonable range
            raise ValueError(f'eGFR value {v} outside expected range (0-200)')
        return v
    
    @validator('unit')
    def validate_unit(cls, v):
        allowed_units = ["mL/min/1.73m2", "mL/min/1.73 m²", "ml/min/1.73m2"]
        if v not in allowed_units:
            # Try to normalize common variations
            v_normalized = v.replace(" ", "").lower()
            if "ml/min" in v_normalized and "1.73" in v_normalized:
                return "mL/min/1.73m2"
            raise ValueError(f'Invalid eGFR unit: {v}')
        return "mL/min/1.73m2"  # Normalize to standard
    
    @validator('test_code')
    def validate_loinc_code(cls, v):
        # Accept common eGFR LOINC codes
        valid_codes = ["98979-8", "33914-3", "62238-1"]
        if v not in valid_codes:
            # Default to CKD-EPI LOINC if unknown
            return "98979-8"
        return v
    
    def get_clinical_stage(self) -> str:
        """Return CKD stage based on eGFR value"""
        if self.result_value >= 90:
            return "G1 - Normal or high"
        elif self.result_value >= 60:
            return "G2 - Mildly decreased"
        elif self.result_value >= 45:
            return "G3a - Mild to moderately decreased"
        elif self.result_value >= 30:
            return "G3b - Moderately to severely decreased"
        elif self.result_value >= 15:
            return "G4 - Severely decreased"
        else:
            return "G5 - Kidney failure"
    
    def needs_clinical_attention(self) -> bool:
        """Returns True if eGFR indicates need for clinical follow-up"""
        return self.result_value < 60  # CKD Stage 3 or worse
    
    def get_risk_level(self) -> str:
        """Return clinical risk level"""
        if self.result_value >= 90:
            return "Low"
        elif self.result_value >= 60:
            return "Low-Moderate" 
        elif self.result_value >= 30:
            return "Moderate-High"
        else:
            return "High"
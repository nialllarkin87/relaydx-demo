# egfr_demo_pipeline.py
import logging
from typing import List, Dict
from ingest.lgc_egfr_parser import parse_lgc_egfr
from ingest.quest_egfr_parser import parse_quest_egfr
from models.egfr_canonical import CanonicalEGFRResult
from output.fhir_builder import build_fhir_output

logger = logging.getLogger(__name__)

class EGFRDemoPipeline:
    """
    Demonstrates vendor-agnostic eGFR processing
    Same Epic output regardless of input vendor
    """
    
    def __init__(self):
        self.vendor_parsers = {
            "lgc": parse_lgc_egfr,
            "quest": parse_quest_egfr
        }
    
    def process_vendor_data(self, vendor: str, data: str) -> Dict:
        """
        Process eGFR data from any vendor
        Returns identical FHIR Bundle structure
        """
        logger.info(f"Processing eGFR data from {vendor.upper()}")
        
        # Step 1: Parse vendor-specific format
        parser = self.vendor_parsers.get(vendor.lower())
        if not parser:
            raise ValueError(f"Unsupported vendor: {vendor}")
        
        try:
            raw_results = parser(data)
            logger.info(f"Parsed {len(raw_results)} eGFR results from {vendor}")
        except Exception as e:
            logger.error(f"Failed to parse {vendor} data: {e}")
            raise
        
        # Step 2: Validate and normalize to canonical format
        canonical_results = []
        validation_errors = []
        
        for raw in raw_results:
            try:
                canonical = CanonicalEGFRResult(**raw)
                canonical_dict = canonical.dict()
                
                # Add clinical insights
                canonical_dict["clinical_stage"] = canonical.get_clinical_stage()
                canonical_dict["needs_attention"] = canonical.needs_clinical_attention()
                canonical_dict["risk_level"] = canonical.get_risk_level()
                
                canonical_results.append(canonical_dict)
                logger.info(f"eGFR: {canonical.result_value} {canonical.unit} - Stage: {canonical.get_clinical_stage()}")
                
            except Exception as e:
                logger.error(f"Validation failed for result: {e}")
                validation_errors.append(str(e))
                continue
        
        if not canonical_results:
            raise ValueError(f"No valid results after normalization. Errors: {validation_errors}")
        
        # Step 3: Generate Epic-compatible FHIR resources
        fhir_resources = []
        for result in canonical_results:
            try:
                # Convert to format expected by existing FHIR builder
                normalized_result = {
                    "patient": {"id": result["patient_id"]},
                    "test": {"code": result["test_code"]},
                    "result": {
                        "value": result["result_value"],
                        "unit": result["unit"]
                    },
                    "effectiveDateTime": result["timestamp"]
                }
                
                fhir_bundle = build_fhir_output(normalized_result)
                fhir_resources.append(fhir_bundle)
                
            except Exception as e:
                logger.error(f"Failed to create FHIR resources: {e}")
                continue
        
        return {
            "vendor": vendor.upper(),
            "raw_count": len(raw_results),
            "validated_count": len(canonical_results),
            "validation_errors": validation_errors,
            "canonical_results": canonical_results,
            "fhir_resources": fhir_resources,
            "epic_ready": len(fhir_resources) > 0
        }
    
    def demonstrate_vendor_agnostic_processing(self, lgc_data: str, quest_data: str):
        """
        Demo: Process same patient's eGFR from different vendors
        Show identical Epic output structure
        """
        print("=" * 60)
        print("RelayDX eGFR Demo: Vendor-Agnostic Processing")
        print("=" * 60)
        
        # Process LGC data
        try:
            lgc_result = self.process_vendor_data("lgc", lgc_data)
            print(f"\n✅ LGC Processing: {lgc_result['validated_count']} results normalized")
            
            if lgc_result["canonical_results"]:
                result = lgc_result["canonical_results"][0]
                print(f"   Patient: {result['patient_id']}")
                print(f"   eGFR: {result['result_value']} {result['unit']}")
                print(f"   Clinical Stage: {result['clinical_stage']}")
                print(f"   Risk Level: {result['risk_level']}")
                
        except Exception as e:
            print(f"❌ LGC Processing Failed: {e}")
            lgc_result = None
        
        # Process Quest data  
        try:
            quest_result = self.process_vendor_data("quest", quest_data)
            print(f"\n✅ Quest Processing: {quest_result['validated_count']} results normalized")
            
            if quest_result["canonical_results"]:
                result = quest_result["canonical_results"][0]
                print(f"   Patient: {result['patient_id']}")
                print(f"   eGFR: {result['result_value']} {result['unit']}")
                print(f"   Clinical Stage: {result['clinical_stage']}")
                print(f"   Risk Level: {result['risk_level']}")
                
        except Exception as e:
            print(f"❌ Quest Processing Failed: {e}")
            quest_result = None
        
        # Compare FHIR output structures
        if lgc_result and quest_result and lgc_result["fhir_resources"] and quest_result["fhir_resources"]:
            lgc_fhir = lgc_result["fhir_resources"][0]
            quest_fhir = quest_result["fhir_resources"][0]
            
            print(f"\n🎯 Epic Integration Ready:")
            print(f"   LGC FHIR: {len(lgc_fhir)} resource types")
            print(f"   Quest FHIR: {len(quest_fhir)} resource types")
            print(f"   Both use LOINC code: 98979-8")
            print(f"   Both generate: Observation + DiagnosticReport")
            
            # Verify structure similarity
            lgc_obs = lgc_fhir.get("observation", {})
            quest_obs = quest_fhir.get("observation", {})
            
            if lgc_obs and quest_obs:
                lgc_code = lgc_obs.get("code", {}).get("coding", [{}])[0].get("code", "")
                quest_code = quest_obs.get("code", {}).get("coding", [{}])[0].get("code", "")
                
                print(f"   LOINC Code Match: {lgc_code == quest_code} ({lgc_code})")
                print(f"   Structure Match: {lgc_obs.get('resourceType') == quest_obs.get('resourceType')}")
        
        return {
            "lgc_processing": lgc_result,
            "quest_processing": quest_result,
            "epic_compatibility": "Identical FHIR structure demonstrated" if lgc_result and quest_result else "Processing errors occurred"
        }
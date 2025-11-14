from typing import List, Dict, Any, Optional
from src.models import IncidentReport
import jsonschema


# JSON Schema for IncidentReport validation
INCIDENT_REPORT_SCHEMA = {
    "type": "object",
    "required": ["title", "summary", "root_cause", "evidence", "fix", "impact", "remaining_risks"],
    "properties": {
        "title": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200
        },
        "summary": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500
        },
        "root_cause": {
            "type": "string",
            "minLength": 10,
            "maxLength": 1000
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 20
        },
        "fix": {
            "type": "string",
            "minLength": 5,
            "maxLength": 1000
        },
        "impact": {
            "type": "string",
            "minLength": 1,
            "maxLength": 500
        },
        "remaining_risks": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10
        },
        "raw_conversation_path": {
            "type": "string"
        }
    }
}


def validate_incident_report(report: IncidentReport) -> List[str]:
    """Validate an IncidentReport and return list of validation errors."""
    errors = []
    
    # Convert to dict for JSON schema validation
    report_dict = {
        "title": report.title,
        "summary": report.summary,
        "root_cause": report.root_cause,
        "evidence": report.evidence,
        "fix": report.fix,
        "impact": report.impact,
        "remaining_risks": report.remaining_risks,
        "raw_conversation_path": report.raw_conversation_path
    }
    
    # Validate against schema
    try:
        jsonschema.validate(report_dict, INCIDENT_REPORT_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
    
    # Additional business logic validation
    if report.title and "incident" not in report.title.lower():
        errors.append("Title should contain 'Incident'")
    
    if not report.evidence:
        errors.append("At least one piece of evidence is required")
    
    if report.root_cause and len(report.root_cause) < 20:
        errors.append("Root cause description is too brief")
    
    # Check for suspicious content
    for evidence in report.evidence:
        if "[REDACTED]" in evidence:
            # This is OK - means PII was properly redacted
            pass
        elif any(pattern in evidence.lower() for pattern in ["password", "secret", "key"]):
            errors.append(f"Evidence may contain sensitive data: {evidence[:50]}...")
    
    return errors


def validate_hypothesis_json(data: Dict[str, Any]) -> List[str]:
    """Validate hypothesis JSON structure from Analyzer."""
    errors = []
    required_fields = ["hypothesis", "evidence", "suspect_files", "fix_suggestion", "confidence"]
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if "confidence" in data:
        try:
            conf = float(data["confidence"])
            if not 0 <= conf <= 1:
                errors.append("Confidence must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append("Confidence must be a number")
    
    if "evidence" in data and not isinstance(data["evidence"], list):
        errors.append("Evidence must be a list")
    
    if "suspect_files" in data and not isinstance(data["suspect_files"], list):
        errors.append("Suspect files must be a list")
    
    return errors


def validate_critic_json(data: Dict[str, Any]) -> List[str]:
    """Validate critic JSON structure."""
    errors = []
    required_fields = ["verdict", "final_report", "remaining_risks"]
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if "verdict" in data and data["verdict"] not in ["confirmed", "revised"]:
        errors.append("Verdict must be 'confirmed' or 'revised'")
    
    if "remaining_risks" in data and not isinstance(data["remaining_risks"], list):
        errors.append("Remaining risks must be a list")
    
    if "final_report" in data:
        report = data["final_report"]
        if not isinstance(report, str):
            errors.append("Final report must be a string")
        elif len(report) > 5000:  # Max ~1000 words
            errors.append("Final report exceeds maximum length")
        elif len(report) < 50:
            errors.append("Final report is too brief")
    
    return errors

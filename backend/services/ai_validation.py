"""
AI Output Validation Layer — Section 11: Failure Handling Architecture
═══════════════════════════════════════════════════════════════════════
Architecture: AI WILL fail sometimes. Always validate AI JSON outputs.

This module validates all AI pipeline outputs against expected schemas,
detects malformed output, handles hallucination signals, and provides
fallback responses for each pipeline.

Validation Rules:
  1. Schema validation — required fields present with correct types
  2. Range validation — scores within expected bounds (0.0-1.0, -1.0 to 1.0)
  3. Consistency check — sentiment label matches score direction
  4. Hallucination signals — confidence too high, impossible claims
  5. Fallback generation — safe defaults when validation fails
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


# ═══════════════════════════════════════════════════
# VALIDATION SCHEMAS
# ═══════════════════════════════════════════════════

# Schema: { "field_name": {"type": type_or_list_of_types, "required": bool, "range": (min, max) or None} }

SENTIMENT_SCHEMA = {
    "sentiment_label": {"type": str, "required": True, "values": ["positive", "negative", "neutral", "mixed"]},
    "sentiment_score": {"type": (int, float), "required": True, "range": (-1.0, 1.0)},
    "emotion": {"type": str, "required": False},
    "emotion_intensity": {"type": (int, float), "required": False, "range": (0, 100)},
    "confidence": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
}

QUALITY_SCHEMA = {
    "quality_score": {"type": (int, float), "required": True, "range": (0.0, 1.0)},
    "clarity": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "depth": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "relevance": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "word_count": {"type": int, "required": False},
    "needs_follow_up": {"type": bool, "required": False},
}

THEME_SCHEMA = {
    "name": {"type": str, "required": True},
    "description": {"type": str, "required": False},
    "sentiment_avg": {"type": (int, float), "required": False, "range": (-1.0, 1.0)},
    "priority": {"type": str, "required": False, "values": ["high", "medium", "low"]},
    "business_risk": {"type": str, "required": False, "values": ["high", "medium", "low"]},
    "is_emerging": {"type": bool, "required": False},
}

RECOMMENDATION_SCHEMA = {
    "title": {"type": str, "required": True},
    "description": {"type": str, "required": False},
    "category": {"type": str, "required": False},
    "priority": {"type": str, "required": False, "values": ["critical", "high", "medium", "low"]},
    "impact_score": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "urgency_score": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "effort_score": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
    "roadmap_phase": {"type": str, "required": False},
}

FOLLOW_UP_SCHEMA = {
    "follow_up": {"type": str, "required": True},
    "intent": {"type": str, "required": False},
    "emotion": {"type": str, "required": False},
    "sentiment_score": {"type": (int, float), "required": False, "range": (-1.0, 1.0)},
    "should_probe_deeper": {"type": bool, "required": False},
}

SEGMENT_SCHEMA = {
    "segment_text": {"type": str, "required": True},
    "topic": {"type": str, "required": False},
    "sentiment_label": {"type": str, "required": False},
    "sentiment_score": {"type": (int, float), "required": False, "range": (-1.0, 1.0)},
}

MEMORY_SCHEMA = {
    "entity": {"type": str, "required": True},
    "relation": {"type": str, "required": False},
    "value": {"type": str, "required": False},
    "confidence": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
}

EXECUTIVE_SUMMARY_SCHEMA = {
    "executive_summary": {"type": str, "required": True},
    "key_findings": {"type": list, "required": False},
    "confidence_score": {"type": (int, float), "required": False, "range": (0.0, 1.0)},
}


# ═══════════════════════════════════════════════════
# PIPELINE → SCHEMA MAPPING
# ═══════════════════════════════════════════════════
PIPELINE_SCHEMAS = {
    # Pipeline B sub-tasks
    ("pipeline_b_response_understanding", "sentiment_analysis"): ("dict", SENTIMENT_SCHEMA),
    ("pipeline_b_response_understanding", "quality_scoring"): ("dict", QUALITY_SCHEMA),
    ("pipeline_b_response_understanding", "response_segmentation"): ("list", SEGMENT_SCHEMA),
    ("pipeline_b_response_understanding", "response_understanding"): ("dict", None),  # Composite — validated internally

    # Pipeline A
    ("pipeline_a_survey_intelligence", "question_generation"): ("dict", None),
    ("pipeline_a_survey_intelligence", "follow_up_generation"): ("dict", FOLLOW_UP_SCHEMA),
    ("pipeline_a_survey_intelligence", "intake_clarification"): ("dict", None),

    # Pipeline C
    ("pipeline_c_insight_formation", "theme_extraction"): ("list", THEME_SCHEMA),
    ("pipeline_c_insight_formation", "insight_clustering"): ("dict", None),
    ("pipeline_c_insight_formation", "memory_extraction"): ("list", MEMORY_SCHEMA),

    # Pipeline D
    ("pipeline_d_recommendation_engine", "recommendation_generation"): ("dict", None),  # Has nested "recommendations" list
    ("pipeline_d_recommendation_engine", "action_plan_generation"): ("dict", None),

    # Pipeline E
    ("pipeline_e_executive_intelligence", "executive_summary"): ("dict", EXECUTIVE_SUMMARY_SCHEMA),
    ("pipeline_e_executive_intelligence", "transcript_report"): ("dict", None),
    ("pipeline_e_executive_intelligence", "trend_analysis"): ("dict", None),
}


# ═══════════════════════════════════════════════════
# AI OUTPUT VALIDATOR
# ═══════════════════════════════════════════════════
class AIOutputValidator:
    """
    Validates all AI pipeline outputs against expected schemas.

    Architecture: Every pipeline output goes through validation before
    being returned to the caller or stored in the database.
    """

    _validations_total = 0
    _validations_passed = 0
    _validations_failed = 0
    _validations_repaired = 0

    @classmethod
    def validate_pipeline_output(cls, pipeline_name: str, task_type: str,
                                 data: Any) -> dict:
        """
        Validate a pipeline output.

        Returns:
            {
                "valid": bool,
                "data": the (possibly repaired) data,
                "warnings": list of warning messages,
                "errors": list of error messages,
            }
        """
        cls._validations_total += 1
        warnings = []
        errors = []

        if data is None:
            cls._validations_failed += 1
            return {
                "valid": False,
                "data": cls._get_fallback(pipeline_name, task_type),
                "warnings": [],
                "errors": ["AI returned None — using fallback"],
            }

        # Look up schema
        schema_key = (pipeline_name, task_type)
        schema_info = PIPELINE_SCHEMAS.get(schema_key)

        if not schema_info:
            # No schema defined — pass through with basic checks
            cls._validations_passed += 1
            return {"valid": True, "data": data, "warnings": [], "errors": []}

        expected_type, field_schema = schema_info

        # ── Type Check ──
        if expected_type == "dict" and not isinstance(data, dict):
            cls._validations_failed += 1
            return {
                "valid": False,
                "data": cls._get_fallback(pipeline_name, task_type),
                "warnings": [],
                "errors": [f"Expected dict, got {type(data).__name__}"],
            }

        if expected_type == "list" and not isinstance(data, list):
            # Try to wrap single dict in list
            if isinstance(data, dict):
                data = [data]
                warnings.append("Wrapped single dict in list")
            else:
                cls._validations_failed += 1
                return {
                    "valid": False,
                    "data": cls._get_fallback(pipeline_name, task_type),
                    "warnings": [],
                    "errors": [f"Expected list, got {type(data).__name__}"],
                }

        if not field_schema:
            cls._validations_passed += 1
            return {"valid": True, "data": data, "warnings": warnings, "errors": []}

        # ── Field-Level Validation ──
        if expected_type == "dict":
            data, field_warnings, field_errors = cls._validate_dict(data, field_schema)
            warnings.extend(field_warnings)
            errors.extend(field_errors)
        elif expected_type == "list":
            repaired_list = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    repaired, fw, fe = cls._validate_dict(item, field_schema)
                    repaired_list.append(repaired)
                    warnings.extend([f"[{i}] {w}" for w in fw])
                    errors.extend([f"[{i}] {e}" for e in fe])
                else:
                    warnings.append(f"[{i}] Non-dict item in list, skipping")
            data = repaired_list if repaired_list else data

        # ── Consistency Checks ──
        if isinstance(data, dict):
            consistency_warnings = cls._check_consistency(data)
            warnings.extend(consistency_warnings)

        # ── Hallucination Detection ──
        hallucination_warnings = cls._check_hallucination_signals(data)
        warnings.extend(hallucination_warnings)

        if errors:
            cls._validations_repaired += 1

        cls._validations_passed += 1
        return {
            "valid": True,  # Repaired if needed
            "data": data,
            "warnings": warnings,
            "errors": errors,
        }

    @classmethod
    def _validate_dict(cls, data: dict, schema: dict) -> tuple:
        """Validate and repair a dict against a field schema."""
        warnings = []
        errors = []

        for field_name, rules in schema.items():
            expected_ftype = rules.get("type")
            required = rules.get("required", False)
            value_range = rules.get("range")
            allowed_values = rules.get("values")

            if field_name not in data:
                if required:
                    errors.append(f"Missing required field '{field_name}'")
                    # Inject default
                    if expected_ftype == str:
                        data[field_name] = ""
                    elif expected_ftype in ((int, float), float, int):
                        data[field_name] = 0
                    elif expected_ftype == bool:
                        data[field_name] = False
                    elif expected_ftype == list:
                        data[field_name] = []
                continue

            value = data[field_name]

            # Type check
            if expected_ftype and not isinstance(value, expected_ftype):
                # Try to coerce
                try:
                    if expected_ftype == (int, float) or expected_ftype == float:
                        data[field_name] = float(value)
                        warnings.append(f"Coerced '{field_name}' to float")
                    elif expected_ftype == int:
                        data[field_name] = int(value)
                        warnings.append(f"Coerced '{field_name}' to int")
                    elif expected_ftype == str:
                        data[field_name] = str(value)
                        warnings.append(f"Coerced '{field_name}' to str")
                    elif expected_ftype == bool:
                        data[field_name] = bool(value)
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_name}' has wrong type: {type(value).__name__}")

            # Range check
            if value_range and isinstance(data.get(field_name), (int, float)):
                val = data[field_name]
                low, high = value_range
                if val < low:
                    data[field_name] = low
                    warnings.append(f"Clamped '{field_name}' from {val} to {low}")
                elif val > high:
                    data[field_name] = high
                    warnings.append(f"Clamped '{field_name}' from {val} to {high}")

            # Allowed values check
            if allowed_values and data.get(field_name) not in allowed_values:
                warnings.append(f"Field '{field_name}' value '{data.get(field_name)}' not in {allowed_values}")

        return data, warnings, errors

    @classmethod
    def _check_consistency(cls, data: dict) -> list:
        """Check logical consistency of AI output."""
        warnings = []

        # Sentiment label should match score direction
        label = data.get("sentiment_label")
        score = data.get("sentiment_score")

        if label and score is not None and isinstance(score, (int, float)):
            if label == "positive" and score < -0.1:
                warnings.append(f"Inconsistency: sentiment_label='positive' but score={score}")
            elif label == "negative" and score > 0.1:
                warnings.append(f"Inconsistency: sentiment_label='negative' but score={score}")

        # Quality score should correlate with sub-scores
        quality = data.get("quality_score")
        clarity = data.get("clarity")
        depth = data.get("depth")
        if (quality is not None and clarity is not None and depth is not None
                and isinstance(quality, (int, float)) and isinstance(clarity, (int, float))
                and isinstance(depth, (int, float))):
            avg_sub = (clarity + depth) / 2
            if abs(quality - avg_sub) > 0.4:
                warnings.append(f"Quality score ({quality}) diverges significantly from sub-scores avg ({round(avg_sub, 2)})")

        return warnings

    @classmethod
    def _check_hallucination_signals(cls, data: Any) -> list:
        """Detect potential hallucination signals in AI output."""
        warnings = []

        if isinstance(data, dict):
            # Suspiciously perfect scores
            confidence = data.get("confidence") or data.get("confidence_score")
            if isinstance(confidence, (int, float)) and confidence >= 0.99:
                warnings.append("Hallucination signal: confidence >= 0.99 (suspiciously high)")

            # All scores exactly the same (lazy AI output)
            numeric_values = [v for v in data.values() if isinstance(v, float) and 0 < v < 1]
            if len(numeric_values) >= 3 and len(set(round(v, 2) for v in numeric_values)) == 1:
                warnings.append("Hallucination signal: all numeric scores identical")

        elif isinstance(data, list):
            # Check if all items are identical (copy-paste hallucination)
            if len(data) >= 3:
                try:
                    str_items = [str(item) for item in data]
                    if len(set(str_items)) == 1:
                        warnings.append("Hallucination signal: all list items identical")
                except Exception:
                    pass

        return warnings

    @classmethod
    def _get_fallback(cls, pipeline_name: str, task_type: str) -> Any:
        """Return safe fallback data when validation fails completely."""
        fallbacks = {
            ("pipeline_b_response_understanding", "sentiment_analysis"): {
                "sentiment_label": "neutral", "sentiment_score": 0.0,
                "emotion": "neutral", "emotion_intensity": 30.0, "confidence": 0.5
            },
            ("pipeline_b_response_understanding", "quality_scoring"): {
                "quality_score": 0.5, "clarity": 0.5, "depth": 0.5,
                "relevance": 0.5, "word_count": 0, "needs_follow_up": True
            },
            ("pipeline_b_response_understanding", "response_segmentation"): [],
            ("pipeline_c_insight_formation", "theme_extraction"): [],
            ("pipeline_c_insight_formation", "memory_extraction"): [],
            ("pipeline_d_recommendation_engine", "recommendation_generation"): {
                "recommendations": [], "summary": "Unable to generate recommendations."
            },
            ("pipeline_e_executive_intelligence", "executive_summary"): {
                "executive_summary": "Report generation failed. Please try again.",
                "key_findings": [], "confidence_score": 0.0
            },
        }

        return fallbacks.get((pipeline_name, task_type), {})

    @classmethod
    def stats(cls) -> dict:
        """Validation statistics."""
        return {
            "total_validations": cls._validations_total,
            "passed": cls._validations_passed,
            "failed": cls._validations_failed,
            "repaired": cls._validations_repaired,
            "pass_rate": round(
                cls._validations_passed / max(cls._validations_total, 1) * 100, 1
            ),
        }

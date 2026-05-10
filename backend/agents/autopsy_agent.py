from typing import Any, Dict
import json
import os

from utils.helpers import clean_ai_response
from utils.logger import log_error, log_info


def get_autopsy_agent():
    """Create Advaith's optional autopsy enrichment agent."""
    try:
        from crewai import Agent
        from dotenv import load_dotenv
        import litellm

        load_dotenv()
        litellm.api_base = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
        litellm.api_key = os.getenv("FEATHERLESS_API_KEY", "mock_key_replace_with_yours")

        return Agent(
            role="Forensic Pathologist",
            goal="Review structured forensic extraction and add cautious investigative interpretation",
            backstory=(
                "You are an experienced forensic pathologist. You do not invent findings. "
                "You review source-backed extraction, highlight medical significance, and state uncertainty."
            ),
            llm_name=f"openai/{os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-7B-Instruct')}",
            temperature=0.1,
            verbose=True,
        )
    except ImportError as e:
        log_error("CrewAI import error", e)
        return None


def analyze_autopsy_report(
    autopsy_text: str,
    structured_findings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Enrich AIVENTRA extraction without replacing source-backed facts."""
    structured_findings = structured_findings or {}

    try:
        from crewai import Task
        from pydantic import BaseModel

        class AutopsyEnrichment(BaseModel):
            interpretive_summary: str
            medical_significance: list
            investigative_considerations: list
            confidence: float

        agent = get_autopsy_agent()
        if not agent:
            return _fallback_autopsy_enrichment(autopsy_text, structured_findings)

        task = Task(
            description=f"""Review this source-backed forensic extraction and add cautious enrichment.

            Do NOT change cause_of_death, injuries, source references, validation flags, or image findings.
            Add only interpretive summary, medical significance, and investigative considerations.

            Structured findings:
            {json.dumps(structured_findings, indent=2)[:5000]}

            Supporting report text:
            {autopsy_text[:2500]}

            Return ONLY valid JSON:
            {{
                "interpretive_summary": "brief cautious summary",
                "medical_significance": ["point1", "point2"],
                "investigative_considerations": ["point1", "point2"],
                "confidence": 0.65
            }}
            """,
            agent=agent,
            output_json=AutopsyEnrichment,
            expected_output="Valid JSON with enrichment only",
        )

        result = task.execute()
        data = json.loads(clean_ai_response(str(result.raw)))
        log_info("[OK] Autopsy enrichment complete")
        return _normalize_enrichment(data)
    except Exception as e:
        log_error("Autopsy enrichment failed, using fallback", e)
        return _fallback_autopsy_enrichment(autopsy_text, structured_findings)


def _fallback_autopsy_enrichment(
    autopsy_text: str,
    structured_findings: Dict[str, Any],
) -> Dict[str, Any]:
    cause = structured_findings.get("cause_of_death") or "undetermined cause of death"
    injuries = structured_findings.get("injuries", [])
    image_count = len(structured_findings.get("image_findings", []))

    significance = []
    text = " ".join([str(cause), " ".join(str(item) for item in injuries), autopsy_text]).lower()
    if any(term in text for term in ["stab", "knife", "sharp"]):
        significance.append("Sharp-force injury pattern should be correlated with weapon recovery and blood-transfer evidence.")
    if any(term in text for term in ["trauma", "blunt", "fracture"]):
        significance.append("Traumatic injury pattern requires scene and witness correlation.")
    if image_count:
        significance.append(f"{image_count} embedded image finding(s) were retained for human forensic review.")
    if not significance:
        significance.append("Medical interpretation is limited by available uploaded evidence.")

    return {
        "interpretive_summary": (
            f"AIVENTRA extraction identifies {cause}. "
            "This enrichment is advisory and should be reviewed against the original report."
        ),
        "medical_significance": significance,
        "investigative_considerations": [
            "Confirm source-backed findings against the original PDF and scene documentation.",
            "Correlate injury timing with CCTV, GPS, witness, and device records.",
        ],
        "confidence": min(float(structured_findings.get("confidence", 0.5) or 0.5), 0.65),
    }


def _normalize_enrichment(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "interpretive_summary": str(data.get("interpretive_summary", "")).strip(),
        "medical_significance": list(data.get("medical_significance", []) or []),
        "investigative_considerations": list(data.get("investigative_considerations", []) or []),
        "confidence": float(data.get("confidence", 0.5) or 0.5),
    }

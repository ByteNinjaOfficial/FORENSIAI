from typing import Dict, Any, List
from sqlalchemy.orm import Session
from models import Case, TimelineEvent, AIResult, RiskFlag, Evidence
from utils.logger import log_info


class ReportGenerator:
    """Generate final investigation report from all analysis"""
    
    @staticmethod
    def generate_report(case_id: str, db: Session) -> Dict[str, Any]:
        """
        Generate comprehensive investigation report
        
        Combines:
        - Case information
        - AI analysis results
        - Timeline reconstruction
        - Risk assessment
        - Recommendations
        """
        
        # Fetch case
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if not case:
            return {"error": "Case not found"}
        
        # Fetch timeline events
        timeline_events = db.query(TimelineEvent).filter(
            TimelineEvent.case_id == case_id
        ).all()
        
        # Fetch AI results
        ai_results = db.query(AIResult).filter(
            AIResult.case_id == case_id
        ).all()
        
        # Fetch risk flags
        risk_flags = db.query(RiskFlag).filter(
            RiskFlag.case_id == case_id
        ).all()

        # Fetch evidence files
        evidence_files = db.query(Evidence).filter(
            Evidence.case_id == case_id
        ).all()
        
        # Extract autopsy data
        autopsy_result = next(
            (r for r in ai_results if r.agent_name == "autopsy_agent"),
            None
        )
        autopsy_data = autopsy_result.result_json if autopsy_result else {}
        
        # Extract correlation data
        correlation_result = next(
            (r for r in ai_results if r.agent_name == "correlation_agent"),
            None
        )
        correlation_data = correlation_result.result_json if correlation_result else {}
        
        # Extract summary
        summary_result = next(
            (r for r in ai_results if r.agent_name == "summary_agent"),
            None
        )
        summary_data = summary_result.result_json if summary_result else {}

        timeline = [
            {
                "timestamp": e.timestamp,
                "source": e.source,
                "event": e.event,
                "severity": e.severity,
                "metadata": e.metadata_json or {}
            }
            for e in timeline_events
        ]

        flags = [
            {
                "name": f.flag_name,
                "description": f.description,
                "score": f.score
            }
            for f in risk_flags
        ]

        recommendations = summary_data.get("recommendations", [])
        injuries = autopsy_data.get("injuries", [])
        toxicology = autopsy_data.get("toxins", []) or autopsy_data.get("toxicology", [])
        anomalies = correlation_data.get("anomalies", [])
        suspicious_patterns = correlation_data.get("suspicious_patterns", [])
        generated_at = str(case.updated_at or case.created_at)
        intelligence = _build_investigative_intelligence(
            case=case,
            autopsy_data=autopsy_data,
            timeline=timeline,
            flags=flags,
            anomalies=anomalies,
            suspicious_patterns=suspicious_patterns,
            limitations=_build_limitations(evidence_files, timeline, anomalies),
            crime_story_override=summary_data.get("crime_story"),
            story_beats_override=summary_data.get("story_beats")
        )

        structured_report = {
            "metadata": {
                "report_title": "ForensiAI Forensic Investigation Report",
                "report_version": "1.0",
                "generated_at": generated_at,
                "generated_by": "ForensiAI Backend",
                "case_status": case.status
            },
            "case_details": {
                "case_id": case.case_id,
                "victim_name": case.victim_name,
                "incident_location": case.incident_location,
                "incident_date": case.incident_date,
                "case_notes": case.notes
            },
            "evidence_summary": {
                "total_files": len(evidence_files),
                "processed_files": len([e for e in evidence_files if e.processed]),
                "files": [
                    {
                        "file_name": e.file_name,
                        "file_type": e.file_type,
                        "processed": e.processed,
                        "uploaded_at": str(e.uploaded_at)
                    }
                    for e in evidence_files
                ]
            },
            "autopsy_findings": {
                "cause_of_death": autopsy_data.get("cause_of_death", "Under investigation"),
                "manner_of_death": autopsy_data.get("manner_of_death", "Not determined"),
                "injuries": injuries,
                "toxicology": toxicology,
                "confidence": autopsy_data.get("confidence", 0.0)
            },
            "timeline_analysis": {
                "total_events": len(timeline),
                "events": timeline
            },
            "correlation_analysis": {
                "anomalies": anomalies,
                "suspicious_patterns": suspicious_patterns,
                "confidence": correlation_data.get("confidence", 0.0)
            },
            "risk_assessment": {
                "risk_level": case.risk_level,
                "risk_score": case.risk_score,
                "flags": flags
            },
            "investigation_summary": {
                "summary": summary_data.get("summary", "Investigation in progress"),
                "recommendations": recommendations,
                "confidence": summary_data.get("confidence", 0.0)
            },
            "investigative_intelligence": intelligence,
            "limitations": intelligence["limitations"]
        }
        
        # Build report
        report = {
            "case_id": case.case_id,
            "victim_name": case.victim_name,
            "incident_location": case.incident_location,
            "incident_date": case.incident_date,
            "status": case.status,
            "summary": summary_data.get("summary", "Investigation in progress"),
            "cause_of_death": autopsy_data.get("cause_of_death", "Under investigation"),
            "manner_of_death": autopsy_data.get("manner_of_death", "Not determined"),
            "injuries": injuries,
            "toxicology": toxicology,
            "timeline": timeline,
            "anomalies": anomalies,
            "suspicious_patterns": suspicious_patterns,
            "risk_level": case.risk_level,
            "risk_score": case.risk_score,
            "flags": flags,
            "recommendations": recommendations,
            "investigative_intelligence": intelligence,
            "case_notes": case.notes,
            "generated_at": generated_at,
            "structured_report": structured_report
        }
        
        log_info(f"[OK] Report generated for case {case_id}")
        
        return report


def _build_limitations(
    evidence_files: List[Evidence],
    timeline: List[Dict[str, Any]],
    anomalies: List[str]
) -> List[str]:
    """Describe missing evidence clearly instead of hiding it in weak results."""
    limitations = []
    uploaded_types = {e.file_type for e in evidence_files}

    if "cctv" not in uploaded_types:
        limitations.append("No CCTV logs were uploaded for this case.")
    if "gps" not in uploaded_types:
        limitations.append("No GPS logs were uploaded for this case.")
    if "metadata" not in uploaded_types:
        limitations.append("No metadata files were uploaded for this case.")
    if len(timeline) <= 1:
        limitations.append("Timeline reconstruction is limited because only autopsy-derived events are available.")

    limitations.extend(anomalies)
    return list(dict.fromkeys(limitations))


def _build_investigative_intelligence(
    case: Case,
    autopsy_data: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
    anomalies: List[str],
    suspicious_patterns: List[str],
    limitations: List[str],
    crime_story_override: str = None,
    story_beats_override: List[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Turn extracted facts into investigator-facing reasoning without inventing unsupported facts."""
    injuries = [str(item) for item in autopsy_data.get("injuries", []) if str(item).strip()]
    cause = str(autopsy_data.get("cause_of_death") or "undetermined")
    manner = str(autopsy_data.get("manner_of_death") or "not determined")
    notes = str(case.notes or "")
    evidence_text = " ".join([cause, manner, notes, " ".join(injuries)]).lower()
    flag_names = {str(flag.get("name", "")).lower() for flag in flags}

    force_level = "unknown"
    if any(term in evidence_text for term in ["sixty", "60", "multiple stab", "multiple injuries", "multiple wound"]):
        force_level = "extreme overkill pattern"
    elif any(term in evidence_text for term in ["stab", "sharp", "knife", "incised"]):
        force_level = "sharp-force assault pattern"
    elif any(term in evidence_text for term in ["trauma", "blunt", "fracture"]):
        force_level = "traumatic assault pattern"

    likely_scene = "Primary scene is not confirmed from available evidence."
    if timeline:
        first = timeline[0]
        likely_scene = (
            f"Earliest available event is from {first.get('source', 'unknown source')} at "
            f"{first.get('timestamp', 'unknown time')}: {first.get('event', 'no event text')}."
        )

    crime_story = crime_story_override if crime_story_override else _compose_crime_story(case, cause, manner, injuries, timeline, force_level, anomalies, limitations)
    breakthrough = _identify_case_breakthrough(force_level, injuries, timeline, flags, evidence_text)

    hypotheses = []
    if "recent_conflict" in flag_names or any(term in evidence_text for term in ["argument", "conflict", "dispute", "stabbed with knife"]):
        hypotheses.append({
            "title": "Known-person or conflict-driven assault",
            "reasoning": "Case notes or risk flags indicate a recent dispute/weapon assault pattern. Prior relationship, threats, calls, and witness accounts should be tested first.",
            "confidence": "medium"
        })
    if force_level == "extreme overkill pattern":
        hypotheses.append({
            "title": "Personal motive or emotionally driven attack",
            "reasoning": "Very high wound count usually deserves a suspect-prioritization review around personal grievance, rage, retaliation, or close-contact escalation.",
            "confidence": "medium"
        })
    if any("gps" in str(event.get("source", "")).lower() or "cctv" in str(event.get("source", "")).lower() for event in timeline):
        hypotheses.append({
            "title": "Movement trail can narrow suspect window",
            "reasoning": "CCTV/GPS entries create a route and timing chain. Police should compare this movement path against last-seen witnesses, vehicle sightings, and phone tower records.",
            "confidence": "medium"
        })
    if not hypotheses:
        hypotheses.append({
            "title": "Evidence-limited homicide/violent death review",
            "reasoning": "Current material supports a violent death review, but suspect direction is limited until scene, witness, CCTV, GPS, call-detail, and weapon evidence are joined.",
            "confidence": "low"
        })

    contradictions = []
    if limitations:
        contradictions.append("Major evidence gaps remain: " + "; ".join(limitations[:3]))
    if len(timeline) <= 1:
        contradictions.append("Timeline is too thin to confirm where the assault began, ended, or whether body discovery location equals offence location.")
    if anomalies:
        contradictions.extend(anomalies[:4])
    if not contradictions:
        contradictions.append("No direct contradiction detected, but this only means uploaded sources did not conflict.")

    next_steps = _build_action_plan(force_level, timeline, injuries, flags, limitations, breakthrough)
    leads = _build_leads(timeline, injuries, evidence_text, limitations)

    return {
        "crime_story": crime_story,
        "story_beats": story_beats_override or [],
        "case_breakthrough": breakthrough,
        "investigative_hypotheses": hypotheses,
        "timeline_interpretation": _interpret_timeline(timeline),
        "contradictions_and_gaps": contradictions,
        "priority_leads": leads,
        "action_plan": next_steps,
        "likely_scene_assessment": likely_scene,
        "limitations": limitations
    }


def _compose_crime_story(
    case: Case,
    cause: str,
    manner: str,
    injuries: List[str],
    timeline: List[Dict[str, Any]],
    force_level: str,
    anomalies: List[str],
    limitations: List[str]
) -> str:
    injury_text = ", ".join(injuries[:6]) if injuries else "no structured injuries were extracted"
    timeline_text = (
        f"The available timeline contains {len(timeline)} event(s), beginning at {timeline[0].get('timestamp')} "
        f"and ending at {timeline[-1].get('timestamp')}."
        if timeline else
        "No reliable movement timeline was available from the uploaded evidence."
    )
    anomaly_text = (
        " Correlation review highlights: " + "; ".join(anomalies[:3]) + "."
        if anomalies else
        ""
    )
    limitation_text = (
        " The reconstruction is limited by: " + "; ".join(limitations[:3]) + "."
        if limitations else
        ""
    )
    return (
        f"Based on the uploaded evidence, {case.victim_name} appears to have suffered {cause.lower()} "
        f"with manner recorded as {manner.lower()}. The injury pattern ({injury_text}) points to a "
        f"{force_level}, not a simple unexplained death. {timeline_text}{anomaly_text}{limitation_text} "
        "The strongest investigative reading is that police should treat the medical findings, movement evidence, "
        "and missing evidence gaps as one combined sequence: establish the victim's last confirmed normal contact, "
        "identify who had access during the injury window, and test whether the body/recovery location matches the assault location."
    )


def _identify_case_breakthrough(
    force_level: str,
    injuries: List[str],
    timeline: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
    evidence_text: str
) -> str:
    if force_level == "extreme overkill pattern":
        return (
            "The possible breakthrough is motive narrowing: the wound pattern suggests rage, retaliation, or a close-contact assault. "
            "Prioritize people with recent conflict, repeated contact, rejected demands, debt/dispute history, or direct access to the victim."
        )
    if any("defensive" in injury.lower() for injury in injuries):
        return (
            "The possible breakthrough is victim resistance: defensive wounds imply the victim saw or confronted the attacker. "
            "Look for suspect injuries, torn clothing, blood transfer, and immediate post-offence medical treatment."
        )
    if timeline and any("cctv" in str(event.get("source", "")).lower() for event in timeline):
        return (
            "The possible breakthrough is route reconstruction: CCTV timestamps should be matched with GPS/phone tower records to isolate who shadowed the victim."
        )
    if any("recent_conflict" in str(flag.get("name", "")).lower() for flag in flags) or "stabbed with knife" in evidence_text:
        return (
            "The possible breakthrough is weapon-source tracing: identify who possessed, bought, borrowed, cleaned, or disposed of a knife near the incident window."
        )
    return (
        "The possible breakthrough is evidence completion: obtain CCTV, GPS, phone records, scene photos, and witness last-seen statements before suspect ranking."
    )


def _interpret_timeline(timeline: List[Dict[str, Any]]) -> List[str]:
    if not timeline:
        return ["No timeline can be reconstructed until movement, scene, or device evidence is uploaded."]
    notes = [
        f"{len(timeline)} event(s) are available. Treat the first and last event as boundary markers, not proof of the full offence window."
    ]
    if len(timeline) >= 2:
        notes.append(
            f"The current boundary runs from {timeline[0].get('timestamp')} to {timeline[-1].get('timestamp')}. Police should search this span for missing sightings, calls, and suspect movement."
        )
    sources = sorted({str(event.get("source", "unknown")) for event in timeline})
    notes.append(f"Timeline sources present: {', '.join(sources)}. Any missing source type weakens the reconstruction.")
    return notes


def _build_leads(
    timeline: List[Dict[str, Any]],
    injuries: List[str],
    evidence_text: str,
    limitations: List[str]
) -> List[str]:
    leads = []
    if any("stab" in injury.lower() or "sharp" in injury.lower() for injury in injuries) or "knife" in evidence_text:
        leads.append("Weapon lead: trace kitchen/workplace knives, recent purchases, disposal spots, cleaned blades, and blood-transfer surfaces.")
    if any("defensive" in injury.lower() for injury in injuries):
        leads.append("Suspect injury lead: check hospitals, clinics, pharmacy purchases, bandages, and witnesses who saw hand/arm cuts after the incident.")
    if timeline:
        leads.append("Movement lead: map every CCTV/GPS timestamp and pull nearby cameras for 30 minutes before and after each point.")
    if any("gps" in item.lower() for item in limitations):
        leads.append("Device lead: collect phone CDR/tower dumps and victim/suspect location history because GPS evidence is missing or incomplete.")
    if any("cctv" in item.lower() for item in limitations):
        leads.append("Scene lead: urgently collect private-shop, traffic, apartment, and fuel-station CCTV before overwrite windows expire.")
    if not leads:
        leads.append("Interview lead: rebuild the final 24 hours using family, coworkers, neighbours, transport records, and digital chats.")
    return leads


def _build_action_plan(
    force_level: str,
    timeline: List[Dict[str, Any]],
    injuries: List[str],
    flags: List[Dict[str, Any]],
    limitations: List[str],
    breakthrough: str
) -> List[Dict[str, str]]:
    actions = [
        {
            "priority": "Immediate",
            "task": "Lock the offence window",
            "why": "Use the first/last reliable sighting, body discovery time, autopsy indicators, calls, CCTV, and GPS to reduce the suspect pool."
        },
        {
            "priority": "Immediate",
            "task": "Test the main breakthrough",
            "why": breakthrough
        }
    ]
    if force_level in {"extreme overkill pattern", "sharp-force assault pattern"}:
        actions.append({
            "priority": "High",
            "task": "Run weapon and blood-transfer investigation",
            "why": "Sharp-force cases often break through weapon recovery, cleaning attempts, clothing stains, disposal routes, and suspect injuries."
        })
    if timeline:
        actions.append({
            "priority": "High",
            "task": "Create a route map",
            "why": "Convert every CCTV/GPS point into a map and look for repeated vehicles, followers, or unexplained stop points."
        })
    if any("defensive" in injury.lower() for injury in injuries):
        actions.append({
            "priority": "High",
            "task": "Search for attacker injury evidence",
            "why": "Defensive injuries increase the chance that the attacker was scratched, cut, bruised, or left touch DNA."
        })
    if limitations:
        actions.append({
            "priority": "Medium",
            "task": "Close evidence gaps",
            "why": "Missing sources can hide contradictions. Collect the unavailable evidence before treating the narrative as complete."
        })
    return actions

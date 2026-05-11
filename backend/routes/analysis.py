from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
import json
from database import get_db
from models import Case, Evidence, AIResult, TimelineEvent, RiskFlag
from schemas.tod_schema import TODInputSchema
from utils.logger import log_info, log_error
from services.pdf_parser import parse_pdf, extract_autopsy_data
from services.csv_parser import parse_and_normalize
from services.timeline_engine import TimelineEngine
from services.risk_engine import RiskEngine
from services.tod_calculator import TODCalculator
from agents.autopsy_agent import analyze_autopsy_report
from agents.correlation_agent import analyze_correlations
from agents.summary_agent import generate_investigation_summary
from datetime import datetime, timedelta
from aiventra.core.image_analyzer import analyze_pdf_images
from aiventra.core.pipeline import run_pipeline
from aiventra.core.video_analyzer import analyze_cctv_video

router = APIRouter(prefix="/cases", tags=["analysis"])


async def process_case_analysis(
    case_id: str,
    tod_input: dict,
    db: Session
):
    """Background task: Execute full forensic analysis pipeline"""
    
    try:
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if not case:
            return
        
        # Clear previous pipeline outputs so re-analysis replaces stale results.
        db.query(AIResult).filter(AIResult.case_id == case_id).delete()
        db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id).delete()
        db.query(RiskFlag).filter(RiskFlag.case_id == case_id).delete()
        db.commit()

        # Update status
        case.status = "processing"
        db.commit()
        
        log_info(f"Starting analysis pipeline for {case_id}")
        
        # ========== PHASE 1: Parse Evidence ==========
        log_info(f"[1/8] Parsing evidence files...")
        
        evidence_files = db.query(Evidence).filter(
            Evidence.case_id == case_id
        ).all()
        
        parsed_evidence = {
            "autopsy": {},
            "autopsy_texts": [],
            "events": [],
            "metadata": {},
            "video_analyses": []
        }
        
        for evidence in evidence_files:
            if not Path(evidence.file_path).exists():
                continue
            
            try:
                if evidence.file_type == "autopsy":
                    # Parse autopsy PDF through the original AIVENTRA forensic
                    # pipeline so section detection, PII redaction, extraction,
                    # validation, and source references are preserved.
                    extracted_autopsy = _analyze_autopsy_with_aiventra(evidence.file_path)
                    if not extracted_autopsy:
                        pdf_data = parse_pdf(evidence.file_path)
                        extracted_autopsy = extract_autopsy_data(pdf_data["text"])

                    parsed_evidence["autopsy_texts"].append(
                        extracted_autopsy.get("raw_text") or extracted_autopsy.get("notes", "")
                    )
                    parsed_evidence["autopsy"] = _merge_autopsy_data(
                        parsed_evidence["autopsy"],
                        extracted_autopsy
                    )
                    evidence.processed = True
                
                elif evidence.file_type == "cctv":
                    if _is_video_file(evidence.file_path):
                        video_result = _analyze_cctv_with_aiventra(evidence.file_path)
                        if video_result:
                            parsed_evidence["video_analyses"].append(video_result)
                            parsed_evidence["events"].extend(
                                _video_result_to_timeline_events(video_result, evidence.file_name)
                            )
                        evidence.processed = True
                    else:
                        events = parse_and_normalize(evidence.file_path, evidence.file_type)
                        parsed_evidence["events"].extend(events)
                        evidence.processed = True

                elif evidence.file_type in ["gps", "metadata"]:
                    # Parse CSV/metadata
                    events = parse_and_normalize(evidence.file_path, evidence.file_type)
                    parsed_evidence["events"].extend(events)
                    evidence.processed = True
                
                db.commit()
            
            except Exception as e:
                log_error(f"Failed to parse {evidence.file_name}", e)
                continue
        
        # ========== PHASE 2: Normalize Data ==========
        log_info(f"[2/8] Normalizing data...")
        
        all_events = parsed_evidence["events"]
        
        # ========== PHASE 3: Time of Death Engine ==========
        log_info(f"[3/8] Calculating time of death...")
        
        tod_result = TODCalculator.estimate_tod(
            body_temperature=tod_input.get("body_temperature"),
            ambient_temperature=tod_input.get("ambient_temperature"),
            rigor_stage=tod_input.get("rigor_stage")
        )
        
        if tod_result["estimated_hours_since_death"] > 0:
            all_events.insert(0, {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "tod_calculation",
                "event": f"Estimated death: {tod_result['estimated_death_window']}",
                "severity": "high",
                "metadata": tod_result
            })
        
        # ========== PHASE 4: Timeline Reconstruction ==========
        log_info(f"[4/8] Reconstructing timeline...")
        
        timeline = TimelineEngine.reconstruct_timeline(all_events)
        
        # Store timeline in database
        for event in timeline:
            timeline_event = TimelineEvent(
                case_id=case_id,
                timestamp=event.get("timestamp", ""),
                source=event.get("source", ""),
                event=event.get("event", ""),
                severity=event.get("severity", "low"),
                metadata_json=event.get("metadata", {})
            )
            db.add(timeline_event)
        db.commit()
        
        log_info(f"[4/8] [OK] Timeline: {len(timeline)} events")
        
        # ========== PHASE 5: Hybrid Autopsy Analysis ==========
        log_info(f"[5/8] AIVENTRA forensic report analysis + autopsy enrichment...")
        
        autopsy_text = "\n\n".join(parsed_evidence.get("autopsy_texts", [])) or (
            parsed_evidence["autopsy"].get("raw_text")
            or parsed_evidence["autopsy"].get("notes", "")
        )
        autopsy_result = parsed_evidence.get("autopsy", {}).copy()
        autopsy_result["notes"] = autopsy_text[:4000]
        autopsy_result["manner_of_death"] = autopsy_result.get("manner_of_death") or parsed_evidence["autopsy"].get("manner_of_death", "")
        autopsy_result.setdefault("cause_of_death", "")
        autopsy_result.setdefault("injuries", [])
        autopsy_result.setdefault("toxicology", [])
        autopsy_result.setdefault("confidence", 0.0)
        enrichment = analyze_autopsy_report(autopsy_text or "Standard autopsy findings", autopsy_result)
        autopsy_result = _merge_autopsy_enrichment(autopsy_result, enrichment)
        
        ai_result = AIResult(
            case_id=case_id,
            # Keep this slot name so Advaith's later report/correlation workflow
            # remains unchanged. The implementation is AIVENTRA extraction plus
            # optional Advaith autopsy-agent enrichment.
            agent_name="autopsy_agent",
            result_json=autopsy_result
        )
        db.add(ai_result)
        
        parsed_evidence["autopsy"] = autopsy_result

        if parsed_evidence["video_analyses"]:
            ai_result = AIResult(
                case_id=case_id,
                agent_name="cctv_video_agent",
                result_json={
                    "videos": parsed_evidence["video_analyses"],
                    "total_videos": len(parsed_evidence["video_analyses"]),
                    "total_events": sum(item.get("total_events", 0) for item in parsed_evidence["video_analyses"]),
                    "analysis_mode": "aiventra_cctv_video_analysis"
                }
            )
            db.add(ai_result)
            db.commit()

        if autopsy_result.get("cause_of_death") or autopsy_result.get("injuries"):
            autopsy_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "autopsy",
                "event": _build_autopsy_timeline_event(autopsy_result),
                "severity": "high",
                "metadata": {
                    "cause_of_death": autopsy_result.get("cause_of_death", ""),
                    "injuries": autopsy_result.get("injuries", []),
                    "confidence": autopsy_result.get("confidence", 0.0)
                }
            }
            timeline.append(autopsy_event)
            db.add(TimelineEvent(
                case_id=case_id,
                timestamp=autopsy_event["timestamp"],
                source=autopsy_event["source"],
                event=autopsy_event["event"],
                severity=autopsy_event["severity"],
                metadata_json=autopsy_event["metadata"]
            ))
            db.commit()
        
        # ========== PHASE 6: Correlation Agent ==========
        log_info(f"[6/8] Correlation analysis...")
        
        evidence_for_correlation = {
            "events": timeline,
            "autopsy": parsed_evidence["autopsy"],
            "video_analysis": parsed_evidence.get("video_analyses", []),
            "witnesses": {}
        }
        
        correlation_result = analyze_correlations(evidence_for_correlation)
        
        ai_result = AIResult(
            case_id=case_id,
            agent_name="correlation_agent",
            result_json=correlation_result
        )
        db.add(ai_result)
        
        parsed_evidence["anomalies"] = correlation_result.get("anomalies", [])
        
        # ========== PHASE 7: Risk Engine ==========
        log_info(f"[7/8] Risk assessment...")
        
        risk_engine = RiskEngine()
        evidence_for_risk = {
            "events": timeline,
            "autopsy": parsed_evidence["autopsy"],
            "video_analysis": parsed_evidence.get("video_analyses", []),
            "anomalies": parsed_evidence.get("anomalies", []),
            "case_notes": case.notes or "",
            "witnesses": {}
        }
        
        risk_assessment = risk_engine.evaluate_risk(evidence_for_risk)
        
        # Store risk flags
        for flag in risk_assessment["flags"]:
            risk_flag = RiskFlag(
                case_id=case_id,
                flag_name=flag["flag"],
                description=flag["description"],
                score=flag["score"]
            )
            db.add(risk_flag)
        
        # Update case risk
        case.risk_level = risk_assessment["risk_level"]
        case.risk_score = risk_assessment["risk_score"]
        
        db.commit()
        
        log_info(f"[7/8] [OK] Risk: {risk_assessment['risk_level']} ({risk_assessment['risk_score']})")
        
        # ========== PHASE 8: Summary Agent ==========
        log_info(f"[8/8] Generating summary...")
        
        summary_data = {
            "cause_of_death": autopsy_result.get("cause_of_death", ""),
            "injuries": autopsy_result.get("injuries", []),
            "events": timeline,
            "video_analysis": parsed_evidence.get("video_analyses", []),
            "anomalies": parsed_evidence.get("anomalies", []),
            "risk_level": risk_assessment["risk_level"]
        }
        
        summary_result = generate_investigation_summary(summary_data)
        
        ai_result = AIResult(
            case_id=case_id,
            agent_name="summary_agent",
            result_json=summary_result
        )
        db.add(ai_result)
        
        # ========== Finalize ==========
        case.status = "completed"
        case.updated_at = datetime.utcnow()
        db.commit()
        
        log_info(f"[OK] Analysis pipeline complete for {case_id}")
    
    except Exception as e:
        log_error(f"Analysis pipeline failed for {case_id}", e)
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if case:
            case.status = "failed"
            db.commit()


def _build_autopsy_timeline_event(autopsy_result: dict) -> str:
    """Create a concise timeline event from autopsy findings."""
    cause = autopsy_result.get("cause_of_death") or "Autopsy findings recorded"
    injuries = autopsy_result.get("injuries", [])
    if injuries:
        return f"{cause}; key injuries: {', '.join(injuries[:4])}"
    return cause


def _is_video_file(file_path: str) -> bool:
    """Detect uploaded CCTV video files instead of treating every CCTV upload as CSV."""
    return Path(file_path).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _analyze_cctv_with_aiventra(file_path: str) -> dict:
    """Run AIVENTRA Track B CCTV analysis and return JSON-safe output."""
    try:
        debug_dir = Path(file_path).parent / "_video_frames"
        result = analyze_cctv_video(
            Path(file_path),
            output_dir=debug_dir,
            sample_fps=1,
        )
        return result.model_dump(mode="json")
    except Exception as e:
        log_error("AIVENTRA CCTV video analysis failed", e)
        return {
            "video_path": str(file_path),
            "events": [],
            "total_events": 0,
            "frames_sampled": 0,
            "motion_frames": 0,
            "yolo_relevant_frames": 0,
            "error": str(e),
        }


def _video_result_to_timeline_events(video_result: dict, file_name: str) -> list[dict]:
    """Convert Track B video events into timeline entries used by reports."""
    events = []
    for item in video_result.get("events", []):
        event_type = item.get("event_type", "cctv_event")
        timestamp_seconds = item.get("timestamp_seconds", 0)
        frame_number = item.get("frame_number", 0)
        description = item.get("event_description", "CCTV event detected")
        confidence = item.get("confidence", 0.0)
        severity = "high" if event_type in {"weapon_visible", "blood_visible"} else "medium"
        event_timestamp = (datetime.utcnow() + timedelta(seconds=float(timestamp_seconds))).isoformat()
        events.append({
            "timestamp": event_timestamp,
            "source": "cctv_video",
            "event": f"{file_name}: {description}",
            "severity": severity,
            "metadata": {
                "event_type": event_type,
                "timestamp_seconds": timestamp_seconds,
                "frame_number": frame_number,
                "confidence": confidence,
                "detected_objects": item.get("detected_objects", []),
                "flags": item.get("flags", []),
            }
        })
    if not events:
        events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "source": "cctv_video",
            "event": (
                f"{file_name}: CCTV video was processed, but no forensic video events "
                "were detected or the analyzer returned fallback-only output."
            ),
            "severity": "low",
            "metadata": {
                "frames_sampled": video_result.get("frames_sampled", 0),
                "motion_frames": video_result.get("motion_frames", 0),
                "yolo_relevant_frames": video_result.get("yolo_relevant_frames", 0),
                "error": video_result.get("error"),
            }
        })
    return events


def _analyze_autopsy_with_aiventra(file_path: str) -> dict:
    """Run the original AIVENTRA forensic report pipeline for FastAPI cases."""
    try:
        result = run_pipeline(Path(file_path), redact_pii=True)
        image_result = _analyze_forensic_report_images(file_path)
        extraction = result.extraction
        preprocessed = result.preprocessed
        return {
            "victim_name": "",
            "age": "",
            "gender": "",
            "cause_of_death": extraction.cause_of_death or "",
            "manner_of_death": extraction.manner_of_death.value if extraction.manner_of_death else "",
            "injuries": [injury.description for injury in extraction.injury_patterns],
            "toxicology": [
                " ".join(
                    part
                    for part in [
                        finding.substance,
                        finding.concentration or "",
                        finding.unit or "",
                    ]
                    if part
                )
                for finding in extraction.toxicology_findings
            ],
            "confidence": extraction.extraction_confidence,
            "notes": preprocessed.raw_text[:4000],
            "raw_text": preprocessed.raw_text,
            "source_references": extraction.source_references,
            "validation_flags": extraction.validation_flags,
            "model_used": result.model_used,
            "aiventra_result": result.model_dump(mode="json"),
            "image_findings": image_result.get("images", []),
            "image_analysis": image_result,
        }
    except Exception as e:
        log_error("AIVENTRA forensic report pipeline failed, falling back to backend parser", e)
        return {}


def _analyze_forensic_report_images(file_path: str) -> dict:
    """Run AIVENTRA embedded-image analysis without interrupting text analysis."""
    try:
        result = analyze_pdf_images(Path(file_path))
        return result.model_dump(mode="json")
    except Exception as e:
        log_error("AIVENTRA forensic image analysis failed", e)
        return {
            "images": [],
            "total_images_extracted": 0,
            "images_analyzed": 0,
            "error": str(e),
        }


def _merge_autopsy_enrichment(base: dict, enrichment: dict) -> dict:
    """Attach Advaith agent enrichment without overriding AIVENTRA facts."""
    merged = base.copy()
    merged["agent_enrichment"] = enrichment
    merged["interpretive_summary"] = enrichment.get("interpretive_summary", "")
    merged["medical_significance"] = enrichment.get("medical_significance", [])
    merged["investigative_considerations"] = enrichment.get("investigative_considerations", [])
    base_confidence = float(base.get("confidence", 0.0) or 0.0)
    enrichment_confidence = float(enrichment.get("confidence", base_confidence) or base_confidence)
    merged["confidence"] = min(base_confidence, enrichment_confidence) if base_confidence else enrichment_confidence
    merged["analysis_mode"] = "aiventra_extraction_plus_autopsy_agent_enrichment"
    return merged


def _merge_autopsy_data(existing: dict, new_data: dict) -> dict:
    """Merge findings from multiple autopsy documents without losing earlier evidence."""
    if not existing:
        return new_data

    merged = existing.copy()
    for key in ["victim_name", "age", "gender", "cause_of_death", "manner_of_death"]:
        if not merged.get(key) and new_data.get(key):
            merged[key] = new_data[key]

    for key in ["injuries", "toxicology", "image_findings", "validation_flags"]:
        combined = list(merged.get(key, [])) + list(new_data.get(key, []))
        seen = set()
        merged[key] = [
            item for item in combined
            if item and not (str(item).lower() in seen or seen.add(str(item).lower()))
        ]

    merged["notes"] = "\n\n".join(filter(None, [merged.get("notes", ""), new_data.get("notes", "")]))[:4000]
    merged["raw_text"] = "\n\n".join(filter(None, [merged.get("raw_text", ""), new_data.get("raw_text", "")]))
    return merged


@router.post("/{case_id}/analyze")
async def analyze_case(
    case_id: str,
    tod_input: TODInputSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger forensic analysis pipeline
    
    Pipeline:
    1. Parse evidence files
    2. Normalize data
    3. Time of Death calculation
    4. Timeline reconstruction
    5. AIVENTRA forensic report analysis
    6. Correlation agent analysis
    7. Risk engine assessment
    8. Summary agent generation
    """
    
    # Verify case exists
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check for evidence
    evidence_count = db.query(Evidence).filter(
        Evidence.case_id == case_id
    ).count()
    
    if evidence_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No evidence files uploaded for this case"
        )
    
    # Start background analysis
    background_tasks.add_task(
        process_case_analysis,
        case_id,
        tod_input.dict(),
        db
    )
    
    log_info(f"[OK] Analysis pipeline started for {case_id}")
    
    return {
        "status": "processing",
        "case_id": case_id,
        "message": "Forensic analysis pipeline started. Poll /results endpoint for completion."
    }

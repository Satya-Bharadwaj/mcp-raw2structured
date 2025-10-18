# raw2structured.py
from __future__ import annotations
import re
import json
import logging
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("raw2structured")

# -------------------------------------------------
#  SECTION CUES
# -------------------------------------------------
SECTION_CUES = {
    "Chief Complaint": ["chief complaint", "presents with", "main concern"],
    "History of Present Illness": ["reports", "complains", "pain", "symptom", "duration", "radiat", "fever", "vomit"],
    "Past Medical History": ["past medical", "history of", "diagnosed", "treated", "previous", "family history"],
    "Current Medications": ["medication", "mg", "tablet", "prescribed", "taking"],
    "Allergies": ["allerg", "reaction", "intolerant", "rash"],
    "Physical Exam": ["exam", "vital", "bp", "hr", "lungs", "abdomen", "neuro"],
    "Labs and Imaging": ["lab", "glucose", "x-ray", "ct", "mri", "ultrasound", "echocardiogram"],
    "Assessment and Plan": ["assessment", "plan", "recommend", "follow-up", "return"],
}

# -------------------------------------------------
#  Sentence splitter (with index)
# -------------------------------------------------
def split_sentences(note: str) -> List[Dict[str, Any]]:
    text = re.sub(r"\s+", " ", note.strip())
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]
    return [{"id": i + 1, "text": s} for i, s in enumerate(sentences)]

# -------------------------------------------------
#  Assign heuristic sections
# -------------------------------------------------
def assign_sections(note: str) -> Dict[str, List[Dict[str, Any]]]:
    sents = split_sentences(note)
    sections = {sec: [] for sec in SECTION_CUES.keys()}

    for sent in sents:
        lsent = sent["text"].lower()
        assigned = False
        for sec_name, kwlist in SECTION_CUES.items():
            if any(kw in lsent for kw in kwlist):
                sections[sec_name].append(sent)
                assigned = True
                break
        if not assigned:
            sections["History of Present Illness"].append(sent)
    return {k: v for k, v in sections.items() if v}

# -------------------------------------------------
#  Build skeleton for structured + citation output
# -------------------------------------------------
def build_structured_framework(note: str) -> Dict[str, Any]:
    sections = assign_sections(note)
    structured_output = {}
    citation_key = []

    for sec_name, sents in sections.items():
        structured_output[sec_name] = []
        for s in sents:
            structured_output[sec_name].append({
                "field": None,
                "value": None,
                "source_ref": f"[{s['id']}]"
            })
            citation_key.append({
                "id": s["id"],
                "text": s["text"]
            })

    return {
        "structured_skeleton": structured_output,
        "citation_key": citation_key,
        "_instructions": (
            "Each section contains empty 'field' and 'value' entries with source_ref pointers. "
            "Your job (LLM host) is to infer meaningful field-value pairs from the raw sentences "
            "and produce Markdown formatted output like the example below:\n\n"
            "### History of Present Illness\n"
            "- Pain character: dull ache in the right upper quadrant [1]\n"
            "- Radiation: radiating to the shoulder [2]\n"
            "\n### Citation Key\n[1] \"Patient reports dull ache...\"\n[2] \"Patient reports dull ache...\""
        )
    }

# -------------------------------------------------
#  MCP TOOL 1 — Segment & Structure
# -------------------------------------------------
@mcp.tool(
    description="Segment raw clinical note, assign sentences to sections, and return a skeleton for structured + citation mapping."
)
def structure_note(note: str) -> Dict[str, Any]:
    return build_structured_framework(note)

# -------------------------------------------------
#  MCP TOOL 2 — Map structured content to FHIR-like resources
# -------------------------------------------------
@mcp.tool(
    description="Map structured clinical content (with field/value pairs) into FHIR-like resource objects such as Condition, Observation, MedicationRequest, etc."
)
def map_to_fhir(structured_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    This function expects structured_content (a dict) with section names
    and lists of { field, value, source_ref } objects as filled by GPT-5.
    It returns a FHIR-like resource bundle.
    """
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }

    # Helper to add resource entries
    def add_resource(resource_type: str, data: Dict[str, Any]):
        fhir_bundle["entry"].append({
            "resource": {
                "resourceType": resource_type,
                **data
            }
        })

    # -------------------------------------------------
    # Defensive parsing and mapping
    # -------------------------------------------------
    for section, items in structured_content.items():
        if not isinstance(items, list):
            continue

        for item in items:
            # 🛡 Handle strings like "Pain: dull ache in RUQ [1]"
            if isinstance(item, str):
                match = re.match(r"^(.*?):\s*(.*?)(?:\s*\[(\d+)\])?$", item)
                if match:
                    field, value, ref = match.groups()
                    item = {
                        "field": field.strip(),
                        "value": value.strip(),
                        "source_ref": f"[{ref}]" if ref else None
                    }
                else:
                    item = {"field": section, "value": item, "source_ref": None}

            # Safely extract
            field = (item.get("field") or "").lower()
            value = item.get("value")
            source = item.get("source_ref")

            if not value:
                continue

            # Map based on section/field heuristics
            if "medication" in field or section.lower().startswith("current medication"):
                add_resource("MedicationRequest", {
                    "medicationCodeableConcept": {"text": value},
                    "note": [{"text": f"From {source}"}]
                })
            elif "allergy" in field or section.lower().startswith("allerg"):
                add_resource("AllergyIntolerance", {
                    "code": {"text": value},
                    "note": [{"text": f"From {source}"}]
                })
            elif "plan" in field or "recommend" in field:
                add_resource("CarePlan", {
                    "description": value,
                    "note": [{"text": f"From {source}"}]
                })
            elif "condition" in field or section.lower().startswith("past medical"):
                add_resource("Condition", {
                    "code": {"text": value},
                    "note": [{"text": f"From {source}"}]
                })
            elif "pain" in field or "symptom" in field or section.lower().startswith("history of present"):
                add_resource("Observation", {
                    "code": {"text": field or "Symptom"},
                    "valueString": value,
                    "note": [{"text": f"From {source}"}]
                })
            else:
                # Default fallback to Observation
                add_resource("Observation", {
                    "code": {"text": field or section},
                    "valueString": value,
                    "note": [{"text": f"From {source}"}]
                })

    return fhir_bundle

# -------------------------------------------------
#  RUN SERVER
# -------------------------------------------------
if __name__ == "__main__":
    logging.info("Starting raw2structured MCP server")
    mcp.run()
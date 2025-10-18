# raw2structured.py
from __future__ import annotations
import re
import json
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("raw2structured")

# -------------------------------------------------
#  Section Detection Helpers
# -------------------------------------------------
SECTION_CUES = {
    "Chief Complaint": ["chief complaint", "presents with", "comes in for", "main concern"],
    "History of Present Illness": ["reports", "complains", "symptom", "duration", "describes", "pain", "fever"],
    "Past Medical History": ["past medical", "history of", "diagnosed", "treated", "suffers", "has"],
    "Current Medications": ["medication", "mg", "tablet", "prescribed", "taking"],
    "Allergies": ["allerg", "reaction", "intolerant", "rash", "tolerates"],
    "Physical Exam": ["exam", "vital", "bp", "hr", "lungs", "cardiac", "abdomen", "neuro", "extremities"],
    "Labs and Imaging": ["lab", "glucose", "hba1c", "ldl", "creatinine", "x-ray", "ct", "mri", "echocardiogram", "ecg"],
    "Assessment and Plan": ["assessment", "plan", "recommend", "continue", "start", "increase", "follow", "return"],
}


def split_sentences(text: str) -> List[str]:
    """Split text into sentences for structured parsing."""
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]


def assign_sections(note: str) -> Dict[str, List[str]]:
    """Assign raw sentences to heuristic sections."""
    sentences = split_sentences(note)
    sections: Dict[str, List[str]] = {k: [] for k in SECTION_CUES.keys()}

    for s in sentences:
        lsent = s.lower()
        assigned = False
        for sec_name, kwlist in SECTION_CUES.items():
            if any(kw in lsent for kw in kwlist):
                sections[sec_name].append(s)
                assigned = True
                break
        if not assigned:
            sections["History of Present Illness"].append(s)

    return {k: v for k, v in sections.items() if v}


# -------------------------------------------------
#  Annotation and Citation Logic
# -------------------------------------------------
def build_structured_note(sections: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Build structured clinical text where each structured line includes
    a numbered citation referring back to the exact raw input sentence.
    """
    structured_lines = []
    citation_map = []
    counter = 1

    for sec, raw_sents in sections.items():
        structured_lines.append(f"### {sec}")
        for sent in raw_sents:
            # Strip whitespace but preserve full raw sentence content
            clean_sent = sent.strip()
            structured_lines.append(f"- {clean_sent} [{counter}]")
            citation_map.append((counter, clean_sent))
            counter += 1
        structured_lines.append("")

    citation_lines = [
        f"[{i}] \"{orig}\" ↩"
        for i, orig in citation_map
    ]

    annotated_summary = "\n".join([
        "## Structured Clinical Note",
        "\n".join(structured_lines),
        "\n## Citation Map (from Raw Input)",
        "\n".join(citation_lines)
    ])

    return {
        "annotated_summary": annotated_summary,
        "citation_map": citation_map
    }


# -------------------------------------------------
#  FHIR Placeholder Template
# -------------------------------------------------
def build_fhir_placeholder(sections: Dict[str, List[str]]) -> Dict[str, Any]:
    """Empty FHIR-like schema for host model to populate."""
    return {
        "Patient": {},
        "Condition": [],
        "Observation": [],
        "MedicationRequest": [],
        "AllergyIntolerance": [],
        "Procedure": [],
        "DiagnosticReport": [],
        "Plan": [],
        "_note_context": {
            "sections": [
                {"name": sec, "sentences": raw_sents}
                for sec, raw_sents in sections.items()
            ],
            "summary_hint": (
                "Each item above references the exact raw text from the input note. "
                "Host LLM should map these factual sentences to appropriate FHIR resources "
                "(Condition, Observation, MedicationRequest, etc.)."
            )
        }
    }


# -------------------------------------------------
#  MCP Tool
# -------------------------------------------------
@mcp.tool(
    description=(
        "Split a raw clinical note into heuristic sections, attach numbered citations "
        "pointing to the exact raw text sentences, and prepare a FHIR-like skeleton. "
        "Does not perform reasoning; host LLM performs entity mapping."
    )
)
def structure_note(note: str) -> Dict[str, Any]:
    sections = assign_sections(note)
    annotated = build_structured_note(sections)
    fhir_skeleton = build_fhir_placeholder(sections)

    fhir_skeleton["annotated_summary"] = annotated["annotated_summary"]
    fhir_skeleton["citation_map"] = annotated["citation_map"]
    return fhir_skeleton


# -------------------------------------------------
#  Run MCP Server
# -------------------------------------------------
if __name__ == "__main__":
    mcp.run()
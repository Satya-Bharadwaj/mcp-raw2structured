# 🧠 MCP Tool: raw2structured

### Overview
`raw2structured` is a **Python-based Model Context Protocol (MCP)** server that transforms **unstructured clinical notes** into a structured, FHIR-like representation.  
It uses deterministic heuristics and semantic cues to segment free-text notes into clinical sections (e.g., *Chief Complaint*, *HPI*, *Medications*, *Allergies*),  
and outputs a **structured skeleton** with sentence-level citations that can be enriched by an LLM layer or mapped into interoperable FHIR resources.

This module forms the **first stage** of the Latitude Health prior authorization workflow:  
→ *Raw note* → **raw2structured** → *structured JSON* → **priorauth-checker** → *eligibility decision*

---

## 🧩 Features

- 🧠 **Heuristic section segmentation** based on contextual cue words  
- 📚 **Sentence-level citation tracing** for explainability and provenance  
- 🔄 **LLM-ready structured skeleton** (`field`, `value`, `source_ref`) for model-assisted completion  
- 🧬 **FHIR mapping** tool that converts structured content into resource bundles  
- 🧰 **MCP-compliant server** that can run standalone or compose into multi-tool AI pipelines  

---

## 🏗️ Architecture

| Layer | Description |
|-------|--------------|
| **Sentence Splitter** | Uses regex-based parsing to tokenize clinical text into indexed sentences |
| **Section Assigner** | Classifies each sentence under heuristic clinical categories (HPI, PMH, etc.) |
| **Structured Framework** | Builds a skeleton JSON with placeholder fields and citation references |
| **FHIR Mapper** | Converts filled JSON into FHIR-like resources (`Condition`, `Observation`, `MedicationRequest`, etc.) |
| **MCP Server** | Exposes both tools (`structure_note`, `map_to_fhir`) via the `FastMCP` protocol |

---


When running, the server exposes two MCP tools:

| Tool | Description |
|------|--------------|
| `structure_note(note: str)` | Segments a free-text note into heuristic sections and outputs a structured skeleton with citations |
| `map_to_fhir(structured_content: dict)` | Maps the structured content (with filled field/value pairs) into a FHIR-like resource bundle |

---

## 🧩 Example Usage

### **Input**
```
Patient presents with chest pain radiating to the shoulder for 2 days.
She reports nausea and mild shortness of breath.
Currently taking metoprolol 25 mg daily.
No known drug allergies.
Plan: Continue beta-blocker and schedule stress test.
```

### **1️⃣ structure_note Output (LLM input skeleton)**
```json
{
  "structured_skeleton": {
    "Chief Complaint": [
      { "field": null, "value": null, "source_ref": "[1]" }
    ],
    "History of Present Illness": [
      { "field": null, "value": null, "source_ref": "[2]" }
    ],
    "Current Medications": [
      { "field": null, "value": null, "source_ref": "[3]" }
    ],
    "Allergies": [
      { "field": null, "value": null, "source_ref": "[4]" }
    ],
    "Assessment and Plan": [
      { "field": null, "value": null, "source_ref": "[5]" }
    ]
  },
  "citation_key": [
    { "id": 1, "text": "Patient presents with chest pain..." },
    { "id": 2, "text": "She reports nausea..." }
  ]
}
```

### **2️⃣ map_to_fhir Output**
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "code": { "text": "Pain" },
        "valueString": "chest pain radiating to the shoulder",
        "note": [{ "text": "From [1]" }]
      }
    },
    {
      "resource": {
        "resourceType": "MedicationRequest",
        "medicationCodeableConcept": { "text": "metoprolol 25 mg daily" },
        "note": [{ "text": "From [3]" }]
      }
    }
  ]
}
```

---

## 🧠 Design Rationale

- **Explainability-first:** Each extracted sentence is traceable via citation keys.  
- **Modularity:** The tool can run standalone, in an LLM loop, or chained via MCP.  
- **Interoperability:** Outputs are aligned with FHIR resource structures.  
- **Safety:** Defensive parsing ensures resilience to malformed text or empty sections.

---

## 📁 File Structure
```
mcp-raw2structured/
├── .gitignore
├── .python-version
├── main.py
├── pyproject.toml
├── raw2structured.py         # MCP server implementation
├── uv.lock
└── README.md
```

---

## 🔗 Related Repositories
- [mcp-priorauth-checker](https://github.com/Satya-Bharadwaj/mcp-priorauth-checker)

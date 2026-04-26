---
name: croissant_expert
description: Specialized in the MLCommons Croissant metadata specification. Can generate, validate, and serialize dataset metadata into compliant JSON-LD.
---

# Croissant Expert Skill

The Croissant Expert skill provides the core logic for working with the [MLCommons Croissant](https://mlcommons.org/croissant) specification. It is responsible for taking dataset descriptions and turning them into 100% compliant JSON-LD metadata files.

Croissant files are stored locally in `./data/croissant/` as JSON-LD files.

## Tools

### 1. Serialize to Croissant JSON-LD
Transforms a structured metadata JSON into the final Croissant format.

**Usage:**
```bash
# Standard serialization
python3 croissant_expert/scripts/serialize.py <INPUT_METADATA_JSON> [OUTPUT_JSON_LD]

# Serialization with Intelligent NLP enrichment
# Automatically detects creators, locations, and dates from the description.
python3 croissant_expert/scripts/serialize.py <INPUT_METADATA_JSON> --nlp
```

**Metadata Schema:**
The input JSON should follow this structure:
- `name`: String
- `description`: String
- `url`: String
- `license`: String
- `distribution`: List of `FileObject` or `FileSet`
- `recordSet`: List of `RecordSet` with `fields` and `source` information.

### 2. Ask Questions on Croissant Metadata
Enables interactive Q&A about a specific dataset using Gemini 2.5 Flash.

**Usage:**
```bash
python3 croissant_expert/scripts/ask.py <CROISSANT_FILE> "How many record sets are defined?"
```

## Capabilities
- **Spec Interpretation**: Access to the latest MLCommons Croissant standard.
- **JSON-LD Generation**: Deep understanding of `@context`, `@type`, and linked data principles.
* **Semantic Analysis**: Can answer complex questions about dataset structure and provenance using LLMs.
- **Validation-Ready**: Output files are designed to pass the official Croissant validator.

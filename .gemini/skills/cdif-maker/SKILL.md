---
name: cdif-maker
description: Interaction with CDIF-dedicated Ollama service to produce structured variable inventories.
---

# CDIF Maker Skill

This skill allows the agent to generate structured CDIF (Cross-Domain Interoperability Framework) variable inventories by querying the specialized Ollama service at `cdif-4-xas.dev.codata.org`.

## Features
- **Semantic Discovery**: Resolves natural language terms (e.g., "soil temperature") into structured technical metadata.
- **Variable Definition**: Returns detailed definitions, unit symbols, and dimensions (time, depth, location).
- **Inventory Generation**: Saves results as standardized JSON files for use in Croissant metadata enrichment.

## Usage
```bash
python3 .gemini/skills/cdif-maker/scripts/cdif_maker.py "soil temperature 10 cm"
```

## Service Details
- **Endpoint**: `https://cdif-4-xas.dev.codata.org/ollama`
- **Default Model**: `gpt-oss:latest`

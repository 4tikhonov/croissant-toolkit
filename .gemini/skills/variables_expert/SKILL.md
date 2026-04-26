---
name: variables_expert
description: Generates high-fidelity CDIF-compliant semantic variable concepts in SKOS / JSON-LD and Markdown formats using local Ollama LLM orchestration natively internally for CODATA projects.
---

# Variables Expert Skill

This skill natively translates natural language measurement claims into comprehensive, CDIF-compliant SKOS concepts. It supports multiple output formats (JSON-LD, Markdown) and ensures all generated variables follow strict naming conventions (e.g., `cdif_` prefixing).

## Prerequisites
Ensure the environment contains valid target routes:
- `OLLAMA_HOST` (Defaults to `http://localhost:11434`)
- `OLLAMA_MODEL` (Defaults to `gpt-oss:latest`)

## Usage Execution

```bash
# Tool usage: Only pass the sentence and format
"For a large fab, maintenance costs can reach $500 million annually." --format json
```

### Advanced Semantic Options
- `--base-url`: Custom namespace for concept IDs.
- `--url`: Provenance URL for the measurement source.
- `--inscheme`: Targeted ontological scheme identifier.
- `--language`: Localization tag for SKOS fields.
- `--format`: Output as `json` (default) or `markdown`.

# Kreuzberg Skill

The **Kreuzberg** skill provides a high-performance, polyglot document intelligence interface for extracting text, metadata, and structured information from 97+ file formats.

## Features
- **Wide Format Support**: PDF, Word, Excel, PowerPoint, academic formats, and 305 programming languages.
- **Structured Output**: Extracts text as GFM (GitHub Flavored Markdown) with support for tables and code blocks.
- **Rust-Powered**: Extreme performance with a Rust core and native PDFium.
- **Intelligence**: Integrated Tree-sitter for code analysis and OCR support for images/PDFs.

## Tools and Scripts

### 1. `extract.py`
A comprehensive extraction tool for processing single files or directories.

**Usage:**
```bash
python3 .gemini/skills/kreuzberg/scripts/extract.py <INPUT_PATH> [OUTPUT_FILE]
```

**Options:**
- `<INPUT_PATH>`: Path to a file or directory.
- `[OUTPUT_FILE]`: (Optional) path to save the extracted Markdown. If omitted, results go to `data/extrated/`.
- `--json`: (Internal) Output full metadata including Croissant JSON-LD.

### 2. `cdif_expert.py`
A semantic mapping tool that converts extracted text into **CDIF-compliant** variables and concepts using Ollama intelligence.

**Usage:**
```bash
python3 .gemini/skills/kreuzberg/scripts/cdif_expert.py data/extracted/<FILENAME>.md
```

## Examples

### Extracting a PDF to Markdown
```bash
python3 .gemini/skills/kreuzberg/scripts/extract.py research_paper.pdf
```

### Processing a DOCX file
```bash
python3 .gemini/skills/kreuzberg/scripts/extract.py legal_contract.docx
```

### Code Intelligence (Python File)
```bash
python3 .gemini/skills/kreuzberg/scripts/extract.py scripts/core.py
```

## Integration with Croissant
The skill automatically generates a Croissant-compatible `FileObject` for the extracted content, ensuring it can be seamlessly integrated into data pipelines.

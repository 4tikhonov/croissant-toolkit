import os
import sys
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

# Try to import kreuzberg
try:
    from kreuzberg import extract_file_sync, ExtractionConfig
except ImportError:
    print("Error: 'kreuzberg' package not found. Please install it using: pip install kreuzberg")
    sys.exit(1)

# Import UNF logic if available
try:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "unf", "scripts"))
    from unf_hash import compute_unf_string
except ImportError:
    compute_unf_string = None

def get_file_hash(file_path):
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_single_file(file_path, output_dir="data/extracted"):
    """Extract text from a single file and generate metadata."""
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False

    print(f"Processing: {file_path.name}...")
    
    try:
        # 1. Extract Text
        config = ExtractionConfig()
        result = extract_file_sync(str(file_path), config=config)
        content = result.content
        metadata_res = result.metadata
        
        # 2. Setup Output Paths
        os.makedirs(output_dir, exist_ok=True)
        meta_dir = os.path.join(output_dir, "metadata")
        os.makedirs(meta_dir, exist_ok=True)
        
        base_name = file_path.stem
        text_out_path = os.path.join(output_dir, f"{base_name}.md")
        meta_out_path = os.path.join(meta_dir, f"{base_name}.json")
        
        # 3. Save Text
        with open(text_out_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # 4. Generate Provenance & Metadata
        file_sha256 = get_file_hash(str(file_path))
        
        # Command Signature (Provenance)
        unf_hash = "N/A"
        if compute_unf_string:
            cmd_str = f"kreuzberg extract {file_path.name}"
            unf_hash = compute_unf_string(cmd_str)

        # Build Croissant-ready metadata
        metadata = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "name": f"Extraction of {file_path.name}",
            "description": f"Text content extracted via Kreuzberg skill from {file_path.name}",
            "datePublished": datetime.utcnow().isoformat() + "Z",
            "contentSignature": unf_hash,
            "distribution": [
                {
                    "@type": "DataDownload",
                    "name": "original_file",
                    "contentUrl": f"file://{file_path.absolute()}",
                    "encodingFormat": "application/octet-stream",
                    "sha256": file_sha256
                },
                {
                    "@type": "DataDownload",
                    "name": "extracted_text",
                    "contentUrl": f"file://{os.path.abspath(text_out_path)}",
                    "encodingFormat": "text/markdown"
                }
            ],
            "extractedMetadata": metadata_res
        }
        
        with open(meta_out_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
            
        print(f"Successfully extracted to: {text_out_path}")
        print(f"Metadata saved to: {meta_out_path}")
        return True

    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract.py <INPUT_PATH> [OUTPUT_DIR]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data/extracted"

    if os.path.isfile(input_path):
        extract_single_file(input_path, output_dir)
    elif os.path.isdir(input_path):
        print(f"Scanning directory: {input_path}")
        for f in os.listdir(input_path):
            f_path = os.path.join(input_path, f)
            if os.path.isfile(f_path):
                extract_single_file(f_path, output_dir)
    else:
        print(f"Error: Invalid path: {input_path}")

if __name__ == "__main__":
    main()

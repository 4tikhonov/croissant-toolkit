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

# Helper for logging failure
def log_failure(action_name, query, reason):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        log_script = os.path.join(skills_dir, "unf", "scripts", "log_provenance.py")
        if os.path.exists(log_script):
            import importlib.util
            spec = importlib.util.spec_from_file_location("log_provenance", log_script)
            log_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(log_module)
            log_module.log_action(action_name, [{"@type": "sc:Text", "value": query}], [], script_path=os.path.abspath(__file__), query=query, status="Failed")
    except Exception:
        pass

def get_file_hash(file_path):
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_single_file(file_path, output_dir="data/extracted", query=None):
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

        # --- Provenance Logging ---
        try:
            script_path_abs = os.path.abspath(__file__)
            skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))
            unf_script_path = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
            log_script_path = os.path.join(skills_dir, "unf", "scripts", "log_provenance.py")
            
            unf_val = None
            if os.path.exists(unf_script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("unf_hash", unf_script_path)
                unf_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(unf_module)
                unf_val = unf_module.compute_unf_file(text_out_path)
                if unf_val:
                    unf_val = unf_val.replace("UNF:6:", "UNF6:")

            if os.path.exists(log_script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("log_provenance", log_script_path)
                log_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(log_module)
                
                inputs = [{"@type": "FileObject", "name": file_path.name, "sha256": file_sha256}]
                outputs = [
                    {"@type": "FileObject", "name": os.path.basename(text_out_path), "unf": unf_val},
                    {"@type": "FileObject", "name": os.path.basename(meta_out_path)}
                ]
                log_module.log_action("extract_text", inputs, outputs, script_path=script_path_abs, query=query or str(file_path), status="Completed")
        except Exception as e:
            print(f"Warning: Provenance logging failed: {e}")

        return True

    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract text from files using Kreuzberg.")
    parser.add_argument("input", help="Path to a file or directory to process.")
    parser.add_argument("--output-dir", default="data/extracted", help="Directory for output files.")
    parser.add_argument("--query", help="Original user query for traceability.")
    args = parser.parse_args()

    input_path = args.input
    output_dir = args.output_dir
    query = args.query or input_path

    if os.path.isfile(input_path):
        extract_single_file(input_path, output_dir, query=query)
    elif os.path.isdir(input_path):
        print(f"Scanning directory: {input_path}")
        for f in os.listdir(input_path):
            f_path = os.path.join(input_path, f)
            if os.path.isfile(f_path):
                extract_single_file(f_path, output_dir, query=query)
    else:
        print(f"Error: Invalid path: {input_path}")

if __name__ == "__main__":
    main()

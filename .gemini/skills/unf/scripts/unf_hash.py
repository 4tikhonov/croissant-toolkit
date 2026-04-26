import os
import sys
import argparse
import json
from pathlib import Path

# Add the local lib/ directory to sys.path to access the UNF library
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

try:
    import polars as pl
except ImportError:
    # Fail silently or log if imported as a library, but error in CLI
    pass

try:
    from dartfx.unf import unf_column, unf_file, unf_dataset
except ImportError:
    pass

def compute_unf_string(input_string):
    """Compute UNF for a single string vector (split and sorted)."""
    import polars as pl
    from dartfx.unf import unf_column
    words = sorted(input_string.split())
    series = pl.Series(words)
    return unf_column(series)

def compute_unf_json(data):
    """Compute UNF for a JSON object by sorting keys and hashing the string."""
    json_str = json.dumps(data, sort_keys=True)
    return compute_unf_string(json_str)

def compute_unf_file(file_path, json_report=False):
    """Compute UNF for a data file (CSV, Parquet, etc.). Falls back to raw string for text files."""
    import polars as pl
    from dartfx.unf import unf_file
    path = Path(file_path)
    if not path.exists():
        print(f"ERROR: File not found: {file_path}")
        return None
    
    try:
        report = unf_file(path)
        if json_report:
            return report.to_json(validate=False)
        else:
            return report.result.unf
    except (ValueError, Exception) as e:
        # Fallback: treat as raw text (single string) if it's not a supported data format
        try:
            content = path.read_text(encoding="utf-8")
            return compute_unf_string(content)
        except Exception as read_err:
            print(f"ERROR: Failed to hash file {file_path}: {e}. Fallback failed: {read_err}")
            return None

def main():
    parser = argparse.ArgumentParser(description="UNF Expert: Compute Universal Numeric Fingerprints (UNF v6).")
    parser.add_argument("input", help="The string to hash or the path to a data file (CSV, Parquet, etc.).")
    parser.add_argument("--json", action="store_true", help="Output a full JSON-LD report instead of just the hash.")
    parser.add_argument("--file", action="store_true", help="Force treating the input as a file path even if it looks like a short string.")
    
    args = parser.parse_args()
    
    if not args.input:
        print("Error: Please provide a string or file path to hash.")
        sys.exit(1)
        
    input_val = args.input
    
    # Heuristic: treat as file if --file is set or if it exists on disk
    if args.file or (os.path.exists(input_val) and os.path.isfile(input_val)):
        result = compute_unf_file(input_val, json_report=args.json)
    else:
        # Treat as string (atomic UNF)
        if args.json:
            print("Note: JSON report format is only available for file/dataset-level hashing. Returning raw hash.")
        result = compute_unf_string(input_val)
        
    if result:
        print(result)

if __name__ == "__main__":
    main()

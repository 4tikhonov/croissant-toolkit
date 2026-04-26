import os
import sys
import json
import argparse
import requests
import re
from datetime import datetime

def fetch_cdif_inventory(term):
    model = "gpt-oss:latest"
    base_url = "https://cdif-4-xas.dev.codata.org/ollama"
    encoded_term = requests.utils.quote(term)
    url = f"{base_url}?term={encoded_term}&model={model}"
    
    try:
        print(f"[CDIF Maker] Requesting inventory for '{term}'...")
        response = requests.get(url, timeout=60)
        
        if response.status_code != 200:
            print(f"[CDIF Maker] API Error {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        return data
        
    except Exception as e:
        print(f"[CDIF Maker] Connection Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="CDIF Maker: Variable Inventory Generator via Specialized AI Service")
    parser.add_argument("term", help="Search term for the variable (e.g. 'soil moisture')")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of pretty report")
    parser.add_argument("--query", help="Original user query for traceability")
    args = parser.parse_args()
    
    term = args.term
    data = fetch_cdif_inventory(term)
    
    if not data:
        print(f"[CDIF Maker] Error: Could not generate CDIF inventory for '{term}'.")
        return
    
    # Sanitize term for filename
    safe_term = re.sub(r'[^a-zA-Z0-9]', '_', term).lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_dir = "data/cdif"
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, f"inventory_{safe_term}_{timestamp}.json")
    
    # --- UNF Fingerprinting ---
    try:
        # Dynamically resolve skills directory (3 levels up from .gemini/skills/cdif-maker/scripts/)
        script_path_abs = os.path.abspath(__file__)
        skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))
        unf_script_path = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
        
        if os.path.exists(unf_script_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("unf_hash", unf_script_path)
            unf_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(unf_module)
            
            # Compute UNF of the data dictionary (excluding itself)
            data_unf = unf_module.compute_unf_json(data)
            if data_unf:
                data["unf"] = data_unf.replace("UNF:6:", "UNF6:")
    except Exception as e:
        print(f"Warning: CDIF fingerprinting failed: {e}")

    with open(report_path, "w") as f:
        json.dump(data, f, indent=4)
    
    # --- Provenance Graph Logging ---
    try:
        log_script_path = os.path.join(skills_dir, "unf", "scripts", "log_provenance.py")
        if os.path.exists(log_script_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("log_provenance", log_script_path)
            log_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(log_module)
            
            inputs = [{"@type": "sc:Text", "value": term}]
            outputs = [{"@type": "FileObject", "name": os.path.basename(report_path), "unf": data.get("unf")}]
            log_module.log_action("generate_cdif_inventory", inputs, outputs, script_path=script_path_abs, query=args.query, status="Completed")
    except Exception as log_err:
        print(f"Warning: Provenance logging failed: {log_err}")

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("\n--- CDIF VARIABLE INVENTORY ---")
        print(f"Name: {data.get('name')}")
        ollama = data.get('ollama', {})
        print(f"Variable: {ollama.get('variable_name')}")
        print(f"Definition: {ollama.get('definition')}")
        
        units = ollama.get('units', {})
        if isinstance(units, dict):
            print(f"Units: {units.get('symbol')} ({units.get('description')})")
        else:
            print(f"Units: {units}")
        
        print(f"\n[CDIF Maker] Success! Inventory saved to: {os.path.abspath(report_path)}")

if __name__ == "__main__":
    main()

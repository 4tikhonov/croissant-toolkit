import json
import os
import sys
import argparse

def audit_provenance(query, output_format="text"):
    """
    Analyzes the provenance graph and reports the status of all actions 
    associated with a specific user query.
    """
    # 1. Resolve dynamic data root based on query UNF
    graph_path = "data/graph/provenance.jsonld"
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.dirname(os.path.dirname(script_dir))
        unf_script = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
        if os.path.exists(unf_script):
            import importlib.util
            spec = importlib.util.spec_from_file_location("unf_hash", unf_script)
            unf_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(unf_mod)
            
            query_unf = unf_mod.compute_unf_string(query)
            if query_unf:
                clean_unf = query_unf.replace("UNF:6:", "").replace("UNF6:", "").replace("/", "_")
                partitioned_path = f"data/{clean_unf}/graph/provenance.jsonld"
                if os.path.exists(partitioned_path):
                    graph_path = partitioned_path
                    # Also set DATA_ROOT for os.walk logic later
                    os.environ["DATA_ROOT"] = f"data/{clean_unf}"
    except Exception as e:
        print(f"Warning: Failed to resolve partitioned graph: {e}", file=sys.stderr)

    if not os.path.exists(graph_path):
        print(f"Error: Provenance graph not found at {graph_path}")
        return

    try:
        with open(graph_path, 'r') as f:
            data = json.load(f)
            graph = data.get("@graph", [])
            context = data.get("@context", {})
    except Exception as e:
        print(f"Error reading provenance graph: {e}")
        return

    # Find activities associated with this query and the query's UNF
    matching_activities = []
    
    # Pre-compute query UNF for comparison
    target_query_unf = "No Fingerprint"
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.dirname(os.path.dirname(script_dir))
        unf_script = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
        if os.path.exists(unf_script):
            import importlib.util
            spec = importlib.util.spec_from_file_location("unf_hash", unf_script)
            unf_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(unf_mod)
            target_query_unf = unf_mod.compute_unf_string(query)
            if target_query_unf:
                target_query_unf = target_query_unf.replace("UNF:6:", "UNF6:")
    except Exception:
        pass

    normalized_query = " ".join(query.lower().split())
    
    for node in graph:
        if node.get("@type") == "prov:Activity":
            used_entities = node.get("prov:used", [])
            if not isinstance(used_entities, list):
                used_entities = [used_entities]
                
            for entity in used_entities:
                # Try matching by UNF first (most reliable)
                e_unf = entity.get("sc:identifier")
                if e_unf and target_query_unf != "No Fingerprint" and e_unf == target_query_unf:
                    matching_activities.append(node)
                    break
                
                # Fallback to normalized value match
                e_val = entity.get("sc:value")
                if e_val:
                    norm_e_val = " ".join(e_val.lower().split())
                    if norm_e_val == normalized_query:
                        matching_activities.append(node)
                        break

    if not matching_activities:
        if output_format == "text":
            print(f"\n[Provenance Expert] No records found for query: \"{query}\"")
        return

    # --- Enrichment and Physical Verification ---
    for activity in matching_activities:
            # 1. Ensure actionStatus is present (default to Completed if missing from older logs)
            if "sc:actionStatus" not in activity:
                activity["sc:actionStatus"] = "sc:CompletedActionStatus"
            
            # 2. Add verification metadata to generated artifacts
            outputs = activity.get("prov:generated", [])
            if not isinstance(outputs, list):
                outputs = [outputs]
            
            for output in outputs:
                file_name = output.get("sc:name")
                if file_name:
                    # Perform physical verification
                    found_path = None
                    file_size = 0
                    data_root = os.environ.get("DATA_ROOT", "data")
                    for root, dirs, files in os.walk(data_root):
                        if file_name in files:
                            found_path = os.path.join(root, file_name)
                            file_size = os.path.getsize(found_path)
                            break
                    
                    if found_path:
                        output["sc:contentSize"] = f"{file_size} B"
                        output["sc:additionalType"] = "https://schema.org/VerifiedFile"
                        
                        # --- Deep Error Analysis ---
                        status_msg = "✅ VERIFIED ON DISK"
                        if file_size == 0:
                            status_msg = "⚠️ EMPTY FILE DETECTED"
                        elif found_path.endswith((".json", ".jsonld")):
                            try:
                                with open(found_path, 'r', encoding='utf-8') as f:
                                    artifact_data = json.load(f)
                                    artifact_str = json.dumps(artifact_data).lower()
                                    if "error" in artifact_str or "timeout" in artifact_str or "fail" in artifact_str:
                                        status_msg = "❌ INTERNAL ERROR DETECTED IN CONTENT"
                                        # Extract error if it's a simple dict
                                        if isinstance(artifact_data, dict) and "error" in artifact_data:
                                            status_msg += f": {artifact_data['error']}"
                                        elif isinstance(artifact_data, dict) and "ollama" in artifact_data and isinstance(artifact_data["ollama"], dict) and "error" in artifact_data["ollama"]:
                                             status_msg += f": {artifact_data['ollama']['error']}"
                            except Exception:
                                pass
                        
                        output["sc:description"] = status_msg
                        # print(f"DEBUG: Set {file_name} desc to {status_msg}")
                    else:
                        output["sc:description"] = "❌ File missing from local storage"

    if output_format == "json-ld":
        # Extract the relevant subgraph
        subgraph = {
            "@context": context,
            "@graph": matching_activities
        }
        print(json.dumps(subgraph, indent=2))
        return

    # Sort activities by start time
    matching_activities.sort(key=lambda x: x.get("prov:startedAtTime", ""))

    print(f"\n" + "="*80)
    print(f"PROVENANCE AUDIT REPORT")
    print(f"Query: \"{query}\"")
    print(f"UNF:   {target_query_unf}")
    print("="*80)

    for i, activity in enumerate(matching_activities, 1):
        name = activity.get("sc:name", "Unnamed Action")
        start_time = activity.get("prov:startedAtTime", "Unknown Time")
        status_val = activity.get("sc:actionStatus", "sc:CompletedActionStatus")
        
        status_text = "✅ SUCCESS" if "Completed" in status_val or "Success" in status_val else "❌ FAILED"
        
        agent = activity.get("prov:wasAssociatedWith", {})
        agent_name = agent.get("sc:name", "Unknown Agent")
        agent_unf = agent.get("sc:identifier", "No Fingerprint")
        agent_did = agent.get("prov:wasAttributedTo", "Unknown DID")

        print(f"\n[{i}] ACTION: {name}")
        print(f"    Status:    {status_text}")
        print(f"    Started:   {start_time}")
        print(f"    Software:  {agent_name} [{agent_unf}]")
        print(f"    Attributed:{agent_did}")
        
        print(f"    Generated Artifacts:")
        outputs = activity.get("prov:generated", [])
        if not isinstance(outputs, list):
            outputs = [outputs]
            
        for output in outputs:
            file_name = output.get("sc:name", "Unknown File")
            unf = output.get("sc:identifier", "No UNF")
            desc = output.get("sc:description", "❌ Not checked")
            
            # Find the path for display
            display_path = file_name
            data_root = os.environ.get("DATA_ROOT", "data")
            for root, dirs, files in os.walk(data_root):
                if file_name in files:
                    full_p = os.path.join(root, file_name)
                    display_path = os.path.relpath(full_p, os.getcwd())
                    break
            
            print(f"      - {file_name} [UNF: {unf}]")
            print(f"        Path: {display_path} -> {desc}")

    print("\n" + "="*80)
    print(f"Audit Complete. Found {len(matching_activities)} verified actions.")
    print("="*80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provenance Expert: Audit action chains from queries.")
    parser.add_argument("query", help="The original user query to audit.")
    parser.add_argument("--format", choices=["text", "json-ld"], default="text", help="Output format.")
    args = parser.parse_args()
    
    audit_provenance(args.query, output_format=args.format)

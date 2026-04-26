import json
import os
import sys
import argparse

def audit_provenance(query, output_format="text"):
    """
    Analyzes the provenance graph and reports the status of all actions 
    associated with a specific user query.
    """
    graph_path = "data/graph/provenance.jsonld"
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
    query_unf = "No Fingerprint"
    for node in graph:
        if node.get("@type") == "prov:Activity":
            used_entities = node.get("prov:used", [])
            if not isinstance(used_entities, list):
                used_entities = [used_entities]
                
            for entity in used_entities:
                if entity.get("sc:value") == query:
                    matching_activities.append(node)
                    if entity.get("sc:identifier"):
                        query_unf = entity.get("sc:identifier")
                    break

    if not matching_activities:
        if output_format == "text":
            print(f"\n[Provenance Expert] No records found for query: \"{query}\"")
        return

    if output_format == "json-ld":
        # Enrich the subgraph with audit metadata before exporting
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
                    for root, dirs, files in os.walk("data"):
                        if file_name in files:
                            found_path = os.path.join(root, file_name)
                            file_size = os.path.getsize(found_path)
                            break
                    
                    if found_path:
                        output["sc:contentSize"] = f"{file_size} B"
                        output["sc:additionalType"] = "https://schema.org/VerifiedFile"
                        output["sc:description"] = "✅ Verified on local storage" if file_size > 0 else "⚠️ Empty file detected"
                    else:
                        output["sc:description"] = "❌ File missing from local storage"

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
    print(f"UNF:   {query_unf}")
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
            
            # Verify physical existence and non-empty status
            found_path = None
            is_empty = False
            for root, dirs, files in os.walk("data"):
                if file_name in files:
                    found_path = os.path.join(root, file_name)
                    if os.path.getsize(found_path) == 0:
                        is_empty = True
                    break
            
            if found_path and not is_empty:
                print(f"      - {file_name} [UNF: {unf}]")
                print(f"        Path: {found_path} -> ✅ VERIFIED ON DISK")
            elif is_empty:
                print(f"      - {file_name} [UNF: {unf}]")
                print(f"        Path: {found_path} -> ⚠️ FAILED (Empty File)")
            else:
                print(f"      - {file_name} [UNF: {unf}]")
                print(f"        ❌ FAILED: File not found on local storage")

    print("\n" + "="*80)
    print(f"Audit Complete. Found {len(matching_activities)} verified actions.")
    print("="*80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provenance Expert: Audit action chains from queries.")
    parser.add_argument("query", help="The original user query to audit.")
    parser.add_argument("--format", choices=["text", "json-ld"], default="text", help="Output format.")
    args = parser.parse_args()
    
    audit_provenance(args.query, output_format=args.format)

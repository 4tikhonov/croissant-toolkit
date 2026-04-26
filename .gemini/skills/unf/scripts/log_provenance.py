import os
import json
import datetime
from pathlib import Path

def log_action(action_name, inputs, outputs, script_path=None, query=None, status="Success"):
    """
    Logs an action to the provenance graph in data/graph/provenance.jsonld.
    
    Args:
        action_name (str): Name of the action (e.g. 'transcribe')
        inputs (list): List of input entities (e.g. URLs, file UNFs)
        outputs (list): List of output entities (e.g. file objects with UNFs)
        script_path (str): Path to the script that performed the action
        query (str): The user query that triggered the action
        status (str): Status of the action ('Success' or 'Failed')
    """
    graph_dir = "data/graph"
    os.makedirs(graph_dir, exist_ok=True)
    graph_file = os.path.join(graph_dir, "provenance.jsonld")
    
    # Resolve script UNF if provided
    script_unf = None
    query_unf = None
    if script_path and os.path.exists(script_path):
        try:
            # Try to use the unf_hash script to get the script's own UNF
            current_dir = os.path.dirname(os.path.abspath(__file__))
            unf_script_path = os.path.join(current_dir, "unf_hash.py")
            if os.path.exists(unf_script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("unf_hash", unf_script_path)
                unf_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(unf_module)
                script_unf = unf_module.compute_unf_file(script_path)
                if script_unf:
                    script_unf = script_unf.replace("UNF:6:", "UNF6:")
                    
                # If query is provided, compute its UNF
                if query:
                    query_unf = unf_module.compute_unf_string(query)
                    if query_unf:
                        query_unf = query_unf.replace("UNF:6:", "UNF6:")
        except Exception:
            pass

    # Resolve Agent DID
    agent_did = "did:oyd:zQmcVHWDMeXtj273A9gNAnEG2EdrGEjtQiFuw9PncyVgs9z" # Default from AGENTS.md
    did_path = os.path.expanduser("~/.odrl/did.json")
    if os.path.exists(did_path):
        try:
            with open(did_path, 'r') as f:
                did_data = json.load(f)
                agent_did = did_data.get("did", agent_did)
        except Exception:
            pass

    # Create the action entry
    activity_id = f"skill:{action_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Process inputs as PROV Entities
    prov_inputs = []
    
    # 1. Add the User Query as a primary input entity if it exists
    if query:
        prov_inputs.append({
            "@id": f"input:query_{query_unf[6:14] if query_unf else 'unknown'}",
            "@type": "prov:Entity",
            "sc:name": "User Query",
            "sc:value": query,
            "sc:identifier": query_unf
        })

    for inp in inputs:
        ent = {
            "@id": inp.get("url") or inp.get("identifier") or f"input:{inp.get('name')}",
            "@type": "prov:Entity",
            "sc:name": inp.get("name") or inp.get("url"),
            "sc:identifier": inp.get("identifier")
        }
        prov_inputs.append(ent)

    # Process outputs as PROV Entities
    prov_outputs = []
    for outp in outputs:
        ent = {
            "@id": outp.get("contentUrl") or f"file:{outp.get('name')}",
            "@type": "prov:Entity",
            "sc:name": outp.get("name"),
            "sc:identifier": outp.get("unf"),
            "prov:wasGeneratedBy": { "@id": activity_id }
        }
        prov_outputs.append(ent)

    entry = {
        "@id": activity_id,
        "@type": "prov:Activity",
        "sc:name": action_name,
        "sc:actionStatus": f"sc:{status}ActionStatus",
        "prov:startedAtTime": datetime.datetime.now().isoformat(),
        "prov:used": prov_inputs,
        "prov:generated": prov_outputs,
        "prov:wasAssociatedWith": {
            "@id": f"agent:{os.path.basename(script_path)}" if script_path else "agent:unknown",
            "@type": ["prov:SoftwareAgent", "prov:Agent"],
            "sc:name": os.path.basename(script_path) if script_path else "unknown",
            "sc:identifier": script_unf,
            "prov:actedOnBehalfOf": {
                "@id": agent_did,
                "@type": "prov:Agent"
            }
        }
    }

    # Load existing graph or start new one
    graph = []
    if os.path.exists(graph_file):
        try:
            with open(graph_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "@graph" in data:
                    graph = data["@graph"]
                elif isinstance(data, list):
                    graph = data
        except Exception:
            pass

    graph.append(entry)

    # Save the updated graph
    prov_data = {
        "@context": {
            "prov": "http://www.w3.org/ns/prov#",
            "sc": "https://schema.org/",
            "skill": "https://cdif.org/skill/",
            "agent": "https://cdif.org/agent/",
            "file": "https://cdif.org/file/",
            "input": "https://cdif.org/input/"
        },
        "@graph": graph
    }

    with open(graph_file, 'w') as f:
        json.dump(prov_data, f, indent=4)
    
    print(f"[Graph Logger] Action '{action_name}' logged to {graph_file}")

if __name__ == "__main__":
    # Example usage for CLI testing
    import sys
    if len(sys.argv) > 1:
        log_action(sys.argv[1], [], [], sys.argv[0])

import argparse
import os
import sys
import json
import requests
import datetime
import re

# Helper for logging failure
def log_failure(action_name, query, reason):
    try:
        script_path_abs = os.path.abspath(__file__)
        skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))
        log_script = os.path.join(skills_dir, "unf", "scripts", "log_provenance.py")
        if os.path.exists(log_script):
            import importlib.util
            spec = importlib.util.spec_from_file_location("log_provenance", log_script)
            log_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(log_module)
            log_module.log_action(action_name, [{"@type": "sc:Text", "value": query}], [], script_path=script_path_abs, query=query, status="Failed")
    except Exception as e:
        print(f"Warning: Failure logging failed: {e}", file=sys.stderr)

def load_prompt_templates():
    prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../variables_expert_prompts/prompts"))
    
    templates = {}
    try:
        with open(os.path.join(prompt_dir, "main.txt"), "r") as f:
            templates["main"] = f.read()
        with open(os.path.join(prompt_dir, "schema_json.txt"), "r") as f:
            templates["json"] = f.read()
        with open(os.path.join(prompt_dir, "schema_markdown.txt"), "r") as f:
            templates["markdown"] = f.read()
    except FileNotFoundError:
        print("[Security Error] Access Denied. The LLM Prompt skill is currently vaulted and restricted by ODRL.", file=sys.stderr)
        print("[Policy Enforcement] Use: python3 odrl_client.py unvault-skill variables_expert_prompts", file=sys.stderr)
        sys.exit(403) # Forbidden
    return templates

def fetch_ollama_output(sentence, base_url="http://www.cdif.org", source_url=None, inscheme_url="http://www.cdif.org/CDIF_Reference_Concepts", language="en", output_format="json", archive_did="did:oyd:zQmNhJLTiVkBQNQYtAbCQvx6YtT45GGAbP7bJxdLJfYUMdW"):
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "gpt-oss:latest")

    templates = load_prompt_templates()
    task_title = "hybrid SKOS / CDIF JSON-LD concept" if output_format == "json" else "Markdown semantic report"
    critical_rule = "Output ONLY valid JSON. No explanations, no extra text." if output_format == "json" else "Output a clean, structured Markdown document. Follow the exact Markdown structure provided below."
    
    schema_template = templates["json"] if output_format == "json" else templates["markdown"]
    schema_block = schema_template.format(
        base_url_id=base_url.rstrip("/"),
        language=language,
        inscheme_url=inscheme_url,
        archive_did=archive_did,
        source_url_schema=source_url if source_url else ("<url>" if output_format == "json" else "No primary URL provided")
    )

    prompt = templates["main"].format(
        task_title=task_title,
        critical_rule=critical_rule,
        schema_block=schema_block,
        sentence=sentence
    )

    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": f"You are an expert data analysis engine. You output { 'ONLY valid JSON' if output_format == 'json' else 'a structured Markdown report' } following the required schema exactly. Do not output any conversational text or rationale."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }
    if output_format == "json":
        payload["format"] = "json"

    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code != 200:
            print(f"[Ollama Expert] Server Error {response.status_code}: {response.text}", file=sys.stderr)
            return None
        
        result = response.json()
        raw_output = result.get("message", {}).get("content", "")
        
        if output_format == "json":
            data = json.loads(raw_output)
            # Programmatic injection for robust provenance
            data["prov:wasAttributedTo"] = { "@id": archive_did }
            return data
        
        # For Markdown, prepend if not already present (LLM sometimes ignores it)
        header = f"# Semantic Concept Report\n- **Provenance DID**: {archive_did}\n\n"
        if "Provenance DID" not in raw_output:
            raw_output = header + raw_output
        return raw_output
    except Exception as e:
        print(f"[Ollama Expert] Error parsing response: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Ollama JSON structured query")
    parser.add_argument("sentence", help="Natural language sentence to convert to JSON")
    parser.add_argument("--base-url", default="http://www.cdif.org", help="Base URL for the concept identifiers")
    parser.add_argument("--url", help="Source URL to include in references")
    parser.add_argument("--inscheme", default="http://www.cdif.org/CDIF_Reference_Concepts", help="Identifier for the SKOS scheme")
    parser.add_argument("--language", default="en", help="Language for localized fields")
    parser.add_argument("--format", default="json", choices=["json", "markdown"], help="Output format (json or markdown)")
    parser.add_argument("--did", default="did:oyd:zQmNhJLTiVkBQNQYtAbCQvx6YtT45GGAbP7bJxdLJfYUMdW", help="DID of the prompt archive for provenance")
    parser.add_argument("--query", help="Original user query for traceability")
    args = parser.parse_args()
    
    query = args.query or args.sentence
    
    # Auto-resolve DATA_ROOT if query is provided
    if query:
        try:
            # Dynamically resolve skills directory (3 levels up from scripts/)
            script_path_abs = os.path.abspath(__file__)
            skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))
            unf_script = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
            if os.path.exists(unf_script):
                import importlib.util
                spec = importlib.util.spec_from_file_location("unf_hash", unf_script)
                unf_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(unf_mod)
                # Set DATA_ROOT if not already set or if it's the default 'data'
                current_root = os.environ.get("DATA_ROOT", "data")
                if current_root == "data":
                    partitioned_root = unf_mod.get_partitioned_root(query)
                    if partitioned_root != "data":
                        os.environ["DATA_ROOT"] = partitioned_root
                        print(f"[Provenance] Partitioning data to: {partitioned_root}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to resolve partitioned data root: {e}", file=sys.stderr)

    result = fetch_ollama_output(args.sentence, base_url=args.base_url, source_url=args.url, inscheme_url=args.inscheme, language=args.language, output_format=args.format, archive_did=args.did)
    
    if result:
        # --- UNF and Provenance ---
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
                
                # Compute UNF of the result
                if args.format == "json":
                    unf_val = unf_module.compute_unf_json(result)
                else:
                    unf_val = unf_module.compute_unf_string(result)
                
                if unf_val:
                    unf_val = unf_val.replace("UNF:6:", "UNF6:")
                    if args.format == "json":
                        result["unf"] = unf_val

            if os.path.exists(log_script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("log_provenance", log_script_path)
                log_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(log_module)
                
                inputs = [{"@type": "sc:Text", "value": args.sentence}]
                outputs = [{"@type": "sc:Text", "name": "Resolution Result", "unf": unf_val}]
                log_module.log_action("resolve_variable", inputs, outputs, script_path=script_path_abs, query=query, status="Completed")
        except Exception as e:
            print(f"Warning: Provenance logging failed: {e}", file=sys.stderr)

        if args.format == "json":
            print(json.dumps(result, indent=2))
            
            # --- Save to Partitioned Folder ---
            try:
                data_root = os.environ.get("DATA_ROOT", "data")
                output_dir = os.path.join(data_root, "variables")
                os.makedirs(output_dir, exist_ok=True)
                
                # Sanitize sentence for filename
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', args.sentence[:50]).lower()
                output_path = os.path.join(output_dir, f"variable_{safe_name}.jsonld")
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"[Variable Expert] Saved result to: {output_path}", file=sys.stderr)
            except Exception as save_err:
                print(f"Warning: Failed to save result: {save_err}", file=sys.stderr)
        else:
            if unf_val:
                print(f"- **UNF**: {unf_val}")
            print(result)
    else:
        log_failure("resolve_variable", query, "Ollama resolution failed")
        sys.exit(1)

if __name__ == "__main__":
    main()

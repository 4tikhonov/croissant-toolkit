import argparse
import os
import sys
import json
import requests
import hashlib
import webbrowser
import rdflib
import re
from bs4 import BeautifulSoup

def load_prompt_templates():
    # Use the same vaulting pattern as json_expert but for baseline skill
    vault_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../vault/baseline.zip"))
    extract_to = os.path.abspath(os.path.join(os.path.dirname(__file__), "../prompts"))
    
    if os.path.exists(vault_path) and not os.listdir(extract_to):
        import subprocess
        # Basic check: if prompts are not extracted, suggest unvaulting
        print(f"[Baseline Expert] Skill is vaulted. Please run 'python3 odrl_client.py unvault-skill baseline'", file=sys.stderr)
        sys.exit(403) # Forbidden
    
    templates = {}
    main_prompt_path = os.path.join(extract_to, "main.txt")
    if os.path.exists(main_prompt_path):
        with open(main_prompt_path, "r") as f:
            templates["main"] = f.read()
    else:
        # Fallback to a core template if main.txt is missing
        templates["main"] = "{task_type}\nInstructions: {instructions}\nReference: {ref_block}\nInput: {input_context}"
    return templates

def fetch_baseline_output(input_context, task="convert", archive_did="did:oyd:zQmNhJLTiVkBQNQYtAbCQvx6YtT45GGAbP7bJxdLJfYUMdW", output_format="json-ld", model="gpt-oss:20b", debug=False):
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    # Priority: Function argument > Environment variable > CLI Default
    actual_model = model or os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
    
    # Extract parameter count (e.g., 20b, 27b, 4b)
    parameter_count = "N/A"
    try:
        match = re.search(r"(\d+b)", actual_model.lower())
        if match:
            parameter_count = match.group(1)
    except:
        pass

    # Parameter-based optimization rule: < 9b models use Markdown communication
    requested_format = output_format
    communication_format = "json-ld" if requested_format in ["json-ld", "rdf", "json-graph"] else requested_format
    param_val = 99 # default high
    try:
        param_val = int(parameter_count.replace("b", ""))
        if param_val < 9:
            communication_format = "markdown"
            print(f"[Baseline Expert] Optimization: Model {actual_model} < 9b. Switching to Markdown communication...", file=sys.stderr)
    except:
        pass

    templates = load_prompt_templates()
    prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../prompts"))
    
    # Task-Specific Prompt Selection
    baseline_prompt_file = "gpt_oss_baseline.txt"
    if task == "analyze":
        baseline_prompt_file = "analyst_baseline.txt"
    elif "gemma" in actual_model.lower():
        baseline_prompt_file = "gemma_baseline.txt"
    
    baseline_prompt_path = os.path.join(prompt_dir, baseline_prompt_file)
    instructions = ""
    if os.path.exists(baseline_prompt_path):
        with open(baseline_prompt_path, "r") as f:
            instructions = f.read()
    else:
        instructions = "Establish a baseline ground truth for the provided input using the CDIF DataDiscovery protocol."

    # Load the gold standard example for structural reference
    example_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../data/samples/exampleCDIFDataDescription.json"))
    example_text = ""
    if os.path.exists(example_path):
        with open(example_path, "r") as f:
            example_text = f.read()

    # Communication optimization for small models (ref_block format)
    if communication_format == "markdown":
        ref_block = (
            "🥇 MANDATORY CDIF RESOLUTION SCHEMA (OUTPUT AS MARKDOWN WITH JSON BLOCK):\n"
            "Your output MUST include a ```json code block``` with the following structure:\n"
            "{\n"
            f"  \"task\": \"{task}\",\n"
            "  \"name\": \"Dataset/Page Title\",\n"
            "  \"description\": \"Extraction/Analysis summary\",\n"
            "  \"detected_claims\": [{\"claim\": \"...\", \"value\": \"...\", \"unit\": \"...\"}],\n"
            "  \"schema:variableMeasured\": [\n"
            "    {\n"
            "      \"name\": \"...\",\n"
            "      \"description\": \"...\",\n"
            "      \"value\": \"...\",\n"
            "      \"unitText\": \"...\",\n"
            "      \"unitCode\": \"...\"\n"
            "    }\n"
            "  ],\n"
            "  \"schema:about\": \"Primary Topic\",\n"
            "  \"schema:genre\": \"Document Genre\"\n"
            "}\n"
            "Focus ONLY on the requested task. DO NOT output ODRL or unrelated metadata."
        )
    else:
        ref_block = f"🥇 GOLD STANDARD EXAMPLE (FOLLOW THIS STRUCTURE):\n{example_text}\n\nOutput ONLY {communication_format.upper()}."

    prompt = templates["main"].format(
        task_type=f"Baseline {task.capitalize()} ({actual_model} - Size: {parameter_count})",
        instructions=instructions,
        ref_block=ref_block,
        input_context=input_context
    )

    if debug:
        print(f"\n{'='*20} DEBUG: FULL LLM PROMPT {'='*20}", file=sys.stderr)
        print(prompt, file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)

    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": actual_model,
        "messages": [
            {
                "role": "system",
                "content": f"You are a CDIF {task.capitalize()} Expert ({parameter_count}). Task: {task.upper()}. Output format: {communication_format.upper()}. Be precise."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }
    
    if communication_format == "json-ld":
        payload["format"] = "json"

    try:
        response = requests.post(url, json=payload, timeout=300)
        if response.status_code != 200:
            print(f"[Baseline Expert] Server Error {response.status_code}: {response.text}", file=sys.stderr)
            return None
        
        result = response.json()
        raw_output = result.get("message", {}).get("content", "")
        
        # Metadata template for consistent attribution
        attribution_meta = {
            "@id": archive_did,
            "schema:softwareVersion": actual_model,
            "schema:parameterCount": parameter_count,
            "status": "SUCCESS",
            "task": task
        }
        
        # Performance check for hallmark hallucinations/placeholders
        is_unreliable = False
        unreliable_markers = ["gobbledegoop", "test data description", "Auto generated from JSON schema", "dummy", "synthetic", "GemmA3B"]
        if any(marker.lower() in raw_output.lower() for marker in unreliable_markers):
            is_unreliable = True
            attribution_meta["status"] = "UNRELIABLE - HALLUCINATION DETECTED"
            print(f"[Baseline Expert] CRITICAL: Hallucinated placeholder detected for model {actual_model}!", file=sys.stderr)

        if requested_format in ["json-ld", "rdf", "json-graph"]:
            try:
                # 🛠️ IMPROVED EXTRACTION FOR < 9b MODELS
                processed_output = raw_output
                if communication_format == "markdown":
                    import re
                    # Look for ```json ... ``` or just { ... }
                    json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
                    if not json_match:
                         # Fallback to finding internal braces
                         json_match = re.search(r"(\{.*?\})", raw_output, re.DOTALL)
                    
                    if json_match:
                         processed_output = json_match.group(1)

                data = json.loads(processed_output)
                data["prov:wasAttributedTo"] = attribution_meta
                
                if is_unreliable:
                    data["schema:comment"] = "This model provided placeholder patterns instead of resolving input."

                # If RDF format requested, manually build the RDF graph using rdflib
                if requested_format in ["rdf", "json-graph"]:
                    from rdflib import Graph, Literal, RDF, URIRef, Namespace
                    from rdflib.namespace import SDO, PROV, XSD
                    
                    CDI = Namespace("http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/")
                    ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
                    EX = Namespace("https://example.org/")
                    
                    g = Graph()
                    g.bind("schema", SDO)
                    g.bind("prov", PROV)
                    g.bind("cdi", CDI)
                    g.bind("odrl", ODRL)
                    g.bind("ex", EX)
                    
                    # Create the main Dataset resource
                    dataset_uri = EX.Dataset
                    if "@id" in data:
                        dataset_uri = URIRef(data["@id"]) if str(data["@id"]).startswith("http") else EX[str(data["@id"]).split(":")[-1]]
                    
                    g.add((dataset_uri, RDF.type, SDO.Dataset))
                    
                    # Map basic fields (Flexible key checks)
                    name = data.get("schema:name") or data.get("name")
                    if name: g.add((dataset_uri, SDO.name, Literal(name)))
                    
                    desc = data.get("schema:description") or data.get("description")
                    if desc: g.add((dataset_uri, SDO.description, Literal(desc)))
                    
                    # Support Analyst Fields
                    about = data.get("schema:about") or data.get("about")
                    if about: g.add((dataset_uri, SDO.about, Literal(about)))
                    
                    genre = data.get("schema:genre") or data.get("genre")
                    if genre: g.add((dataset_uri, SDO.genre, Literal(genre)))
                    
                    keywords = data.get("schema:keywords") or data.get("keywords") or []
                    if isinstance(keywords, list):
                        for kw in keywords: g.add((dataset_uri, SDO.keywords, Literal(kw)))
                    elif keywords:
                        g.add((dataset_uri, SDO.keywords, Literal(keywords)))

                    url_val = data.get("schema:url") or data.get("url")
                    if url_val: g.add((dataset_uri, SDO.url, URIRef(url_val)))

                    # Map Claims
                    for i, claim in enumerate(data.get("detected_claims", []) or data.get("claims", [])):
                        claim_uri = EX[f"claim_{i}"]
                        g.add((dataset_uri, EX.detected_claims, claim_uri))
                        text_val = claim.get("claim") or claim.get("text") or ""
                        g.add((claim_uri, SDO.text, Literal(text_val)))
                        
                        val = claim.get("value")
                        if val: g.add((claim_uri, SDO.value, Literal(val)))
                        
                        unit = claim.get("unit")
                        if unit: g.add((claim_uri, SDO.unitText, Literal(unit)))
                        
                        g.add((var_uri, RDF.type, CDI.InstanceVariable))
                        g.add((var_uri, SDO.name, Literal(var.get("name", var.get("schema:name", "")))))
                        g.add((var_uri, SDO.description, Literal(var.get("description", var.get("schema:description", "")))))
                        g.add((dataset_uri, SDO.variableMeasured, var_uri))
                        
                        v_unit = var.get("schema:unitText") or var.get("unitText") or var.get("unitCode")
                        if v_unit: g.add((var_uri, SDO.unitText, Literal(v_unit)))
                        
                        v_code = var.get("schema:unitCode") or var.get("unitCode")
                        if v_code: g.add((var_uri, SDO.unitCode, Literal(v_code)))
                        
                        v_val = var.get("schema:value") or var.get("value")
                        if v_val: g.add((var_uri, SDO.value, Literal(v_val)))
                        
                        v_min = var.get("schema:minValue") or var.get("minValue")
                        if v_min: g.add((var_uri, SDO.minValue, Literal(v_min, datatype=XSD.float)))
                        
                        v_max = var.get("schema:maxValue") or var.get("maxValue")
                        if v_max: g.add((var_uri, SDO.maxValue, Literal(v_max, datatype=XSD.float)))

                    # Map Provenance
                    did_uri = URIRef(archive_did)
                    g.add((dataset_uri, PROV.wasAttributedTo, did_uri))
                    g.add((did_uri, SDO.softwareVersion, Literal(actual_model)))
                    g.add((did_uri, EX.parameterCount, Literal(parameter_count)))
                    g.add((did_uri, EX.resolutionStatus, Literal(attribution_meta["status"])))
                    g.add((did_uri, EX.task, Literal(task)))

                    if requested_format == "json-graph":
                        # Explicit context for high-fidelity JSON-LD Graph serialization
                        ctx = {
                            "schema": "https://schema.org/",
                            "prov": "http://www.w3.org/ns/prov#",
                            "cdi": "http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/",
                            "ex": "https://example.org/",
                            "detected_claims": "ex:detected_claims",
                            "variableMeasured": "schema:variableMeasured"
                        }
                        return g.serialize(format='json-ld', context=ctx, indent=2)
                    
                    return g.serialize(format='turtle')

                # Validation counts
                claims_count = len(data.get("detected_claims", []))
                vars_count = len(data.get("schema:variableMeasured", []))
                if claims_count != vars_count and claims_count > 0:
                    print(f"[Baseline Expert] WARNING: Quantitative Mismatch!", file=sys.stderr)
                
                return data
            except Exception as e:
                if requested_format in ["rdf", "json-graph"]:
                    print(f"[Baseline Expert] RDF Conversion Error: {e}", file=sys.stderr)
                
                # If JSON failed, still return a meaningful structure for auditing
                s_status = attribution_meta["status"]
                if communication_format == "markdown":
                     s_status = "MARKDOWN REDIRECTION"
                else:
                     s_status = "FAILED - BROKEN JSON"

                return {
                    "raw_output": raw_output,
                    "status": s_status,
                    "prov:wasAttributedTo": attribution_meta,
                    "schema:comment": "The model produced non-JSON output (optimized for < 9b logic)." if communication_format == "markdown" else "The model produced malformed JSON."
                }
        
        # Handle Markdown with attribution headers
        header = f"# CDIF Baseline {task.capitalize()} Report\n- **Model**: {actual_model}\n- **Status**: {attribution_meta['status']}\n\n"
        return header + raw_output
    except Exception as e:
        print(f"[Baseline Expert] Error: {e}", file=sys.stderr)
        return None

def extract_claim_from_line(model, base_prompt, line, debug=False):
    """Specific prompt for individual sentence extraction."""
    instr = (
        "Task: Determine if the following sentence contains a SPECIFIC QUANTITATIVE MEASUREMENT, TIMEFRAME, or CURRENCY VALUE.\n"
        "If NO measurement exists, output ONLY 'NULL'.\n"
        "If YES, output ONLY a JSON object: "
        "{\"claim\": \"Description of the measurement\", \"value\": \"The number or range\", \"unitText\": \"weeks/date/USD/etc\", \"name\": \"variable name\", \"description\": \"context\"}\"\n"
        f"Input Sentence: {line}"
    )
    
    try:
        response = fetch_baseline_output(instr, model=model, task="convert", output_format="json-ld")
        if debug:
            print(f"[PCE Worker] Input: {line[:30]}... -> Output: {str(response)[:100]}", file=sys.stderr)
        
        # Parse logic
        data = None
        if isinstance(response, dict):
            data = response
        elif isinstance(response, str) and "{" in response:
            import json
            try:
                clean_json = response.strip().replace("```json", "").replace("```", "")
                data = json.loads(clean_json)
            except: pass
            
        if data and data.get("value") and str(data.get("value")).upper() not in ["NULL", "TRUE", "FALSE", "UNKNOWN"]:
            # Additional heuristic: value should contain a digit if it's a measurement (often)
            # but for things like 'shortly' we might want it too. 
            # Let's trust the model if it provided a value that isn't just a boolean.
            return data
    except Exception as e:
        if debug: print(f"[PCE Worker] Error: {e}", file=sys.stderr)
    return None

def _get_clean_sentences(html_text):
    if not html_text:
        return set()
    soup = BeautifulSoup(html_text, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    
    raw_text = soup.get_text(separator=' ', strip=True)
    sentences = re.split(r'[\n;.]', raw_text)
    # Filter for fragments > 3 words
    return [s.strip() for s in sentences if s.strip() and len(s.strip().split()) > 3]

def fetch_url_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/120.0.0.0'
    }
    try:
        # 1. Fetch Target Page
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403:
            print(f"[Baseline Expert] 403 Forbidden. Attempting to open URL in browser as fallback...", file=sys.stderr)
            webbrowser.open(url)
        response.raise_for_status()
        target_html = response.text
        target_lines = _get_clean_sentences(target_html)
        
        # 2. Fetch Comparison Page (Domain Root) for De-Boilerplating
        from urllib.parse import urlparse
        parsed = urlparse(url)
        root_url = f"{parsed.scheme}://{parsed.netloc}/"
        
        comparison_lines = set()
        if root_url != url:
            try:
                comp_response = requests.get(root_url, headers=headers, timeout=15)
                if comp_response.status_code == 200:
                    comparison_lines = set(_get_clean_sentences(comp_response.text))
                    print(f"[Baseline Expert] Differential De-Boilerplating: Removed {len([l for l in target_lines if l in comparison_lines])} common blocks.", file=sys.stderr)
            except:
                pass # Fallback to target only if root fails
        
        # 3. Filter Target Lines
        final_lines = [line for line in target_lines if line not in comparison_lines]
        
        return final_lines
    except Exception as e:
        print(f"[Baseline Expert] Error fetching URL: {e}", file=sys.stderr)
        return []

def main():
    from concurrent.futures import ThreadPoolExecutor
    parser = argparse.ArgumentParser(description="CDIF Baseline Evaluation Skill v2.0")
    parser.add_argument("input", nargs="?", help="Description or JSON to process")
    parser.add_argument("--url", help="URL to process")
    parser.add_argument("--model", default="gpt-oss:20b", help="Model: gpt-oss:20b or gemma3:27b")
    parser.add_argument("--format", default="json-ld", choices=["json-ld", "markdown", "rdf", "json-graph"])
    parser.add_argument("--task", default="convert", choices=["convert", "analyze"], help="Task: convert (extract) or analyze (classify)")
    parser.add_argument("--did", default="did:oyd:zQmNhJLTiVkBQNQYtAbCQvx6YtT45GGAbP7bJxdLJfYUMdW", help="Archive DID")
    parser.add_argument("--debug", type=str, default="false", help="Print debug/input transparency logs")
    parser.add_argument("--parallel", type=str, default="false", help="Query model one-by-one sentence in parallel")
    args = parser.parse_args()
    
    is_debug = args.debug.lower() == "true"
    parallel = args.parallel.lower() == "true"
    
    input_content = []
    if args.url:
        print(f"[Baseline Expert] Fetching content from URL: {args.url}...", file=sys.stderr)
        input_content = fetch_url_text(args.url)
    elif args.input:
        if os.path.isfile(args.input):
            with open(args.input, "r") as f:
                input_content = f.read()
        else:
            input_content = args.input
    else:
        print("[JSON Expert] Error: Either 'input' argument or '--url' parameter must be provided.", file=sys.stderr)
        sys.exit(1)
        
    if not input_content:
        sys.exit(1)

    if is_debug:
        print(f"\n{'='*20} DEBUG: PARSED INPUT (LINES: {len(input_content) if isinstance(input_content, list) else 1}) {'='*20}", file=sys.stderr)
        preview = input_content[:10] if isinstance(input_content, list) else input_content[:1000]
        print(preview, file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)

    # 2. Parallel Extraction if requested
    if parallel and isinstance(input_content, list):
        print(f"[Baseline Expert] PCE Active. Synchronizing {len(input_content)} semantic lines...", file=sys.stderr)
        claims = []
        variables = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(extract_claim_from_line, args.model, "", line, is_debug) for line in input_content]
            for future in futures:
                res = future.result()
                if res and (res.get("claim") or res.get("name")):
                    claims.append({"claim": res.get("claim"), "value": res.get("value"), "unit": res.get("unitText")})
                    variables.append({
                        "name": res.get("name") or res.get("claim"),
                        "description": res.get("description"),
                        "unitText": res.get("unitText"),
                        "value": res.get("value")
                    })
        
        # Synthesize manually
        final_data = {
            "task": args.task,
            "name": "Synthesized Dataset Analysis",
            "description": f"Parallelly extracted claims from {len(input_content)} lines.",
            "detected_claims": claims,
            "schema:variableMeasured": variables,
            "schema:about": "Aggregated Content Audit",
            "schema:genre": "AggregatedAudit",
            "prov:wasAttributedTo": {
                "@id": args.did,
                "schema:softwareVersion": args.model,
                "status": "SUCCESS",
                "task": args.task,
                "mode": "parallel"
            }
        }
        
        # Handle format
        if args.format == "rdf":
            # Repurpose existing logic to output RDF from dict
            # (Simplification: just print the dict for now, or I can call the same logic)
            print(json.dumps(final_data, indent=2)) # TODO: Formal RDF synthesis if needed
        else:
            print(json.dumps(final_data, indent=2))
    else:
        # Monolithic fallback
        monolithic_input = "\n".join(input_content) if isinstance(input_content, list) else input_content
        result = fetch_baseline_output(monolithic_input, task=args.task, output_format=args.format, model=args.model, archive_did=args.did, debug=is_debug)
        if result:
            if args.format == "json-ld" and isinstance(result, dict):
                print(json.dumps(result, indent=2))
            else:
                print(result)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()

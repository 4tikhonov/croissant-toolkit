import subprocess
import json
import os
import sys

# Configuration
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "cdif_variable.py"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://10.147.18.82:8093")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
TEST_DID = "did:oyd:zQmNhJLTiVkBQNQYtAbCQvx6YtT45GGAbP7bJxdLJfYUMdW"

def run_expert(sentence, format="json", language="en"):
    env = os.environ.copy()
    env["OLLAMA_HOST"] = OLLAMA_HOST
    env["OLLAMA_MODEL"] = OLLAMA_MODEL
    
    cmd = [
        "python3", SCRIPT_PATH, 
        sentence, 
        "--format", format, 
        "--language", language,
        "--did", TEST_DID
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Script execution failed: {e.stderr}")
        return None

def test_json_ld_structure():
    print("\n--- Testing JSON-LD Structure ---")
    sentence = "For a large fab, maintenance costs can reach $500 million annually."
    output = run_expert(sentence, format="json")
    
    if not output:
        print("FAIL: No output returned.")
        return False
    
    try:
        data = json.loads(output)
        
        # Check mandatory SKOS / CDIF fields
        required_fields = ["@id", "@type", "prefLabel", "definition", "prov:wasAttributedTo", "variable_name", "variablecascade"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"FAIL: Missing fields: {missing}")
            return False
            
        if not data["variable_name"].startswith("cdif_"):
            print(f"FAIL: variable_name '{data['variable_name']}' does not start with 'cdif_'.")
            return False
            
        if data["prov:wasAttributedTo"]["@id"] != TEST_DID:
            print("FAIL: Incorrect provenance DID in output.")
            return False
            
        print("PASS: JSON-LD structure verified.")
        return True
    except json.JSONDecodeError:
        print("FAIL: Output is not valid JSON.")
        return False

def test_markdown_presentation():
    print("\n--- Testing Markdown Presentation ---")
    sentence = "Anthropic took down thousands of GitHub repos after source code leak."
    output = run_expert(sentence, format="markdown")
    
    if not output:
        print("FAIL: No output returned.")
        return False
    
    # Check for formatting hallmarks
    checks = {
        "Header": "# Semantic Concept Report",
        "Provenance": f"Provenance DID: {TEST_DID}",
        "Table": "| Attribute | Specification |",
        "Section": "## Variable Cascade",
        "Prefix": "cdif_"
    }
    
    failed = [k for k, v in checks.items() if v not in output]
    if failed:
        print(f"FAIL: Markdown missing expected elements: {failed}")
        # print(f"DEBUG: Output trace:\n{output}")
        return False
        
    print("PASS: Markdown presentation verified.")
    return True

def test_language_localization():
    print("\n--- Testing Language Localization (en) ---")
    sentence = "Chip manufacturing costs are increasing."
    output = run_expert(sentence, language="en")
    
    if not output: return False
    
    data = json.loads(output)
    if data["prefLabel"]["@language"] != "en":
        print(f"FAIL: Incorrect language tag: {data['prefLabel']['@language']}")
        return False
        
    print("PASS: Language localization verified.")
    return True

def main():
    # Pre-test check: ensures prompts are unvaulted
    print("[Test Suite] Preparing Variables Expert verification cycle...")
    
    # Verify unvaulting
    try:
        subprocess.run(["python3", "odrl_client.py", "unvault-skill", "variables_expert_prompts"], check=True)
    except:
        print("[CRITICAL] Could not unvault prompts. Testing cannot proceed.")
        sys.exit(1)
        
    success = True
    success &= test_json_ld_structure()
    success &= test_markdown_presentation()
    success &= test_language_localization()
    
    # Final check: re-vault for security
    print("\n[Test Suite] Securing prompts post-test...")
    subprocess.run(["python3", "odrl_client.py", "vault-skill", "variables_expert_prompts"], check=True)
    
    if success:
        print("\n🏆 ALL TESTS PASSED: Variables Expert is operational and CDIF-compliant.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED: Expert requires diagnostic audit.")
        sys.exit(1)

if __name__ == "__main__":
    main()

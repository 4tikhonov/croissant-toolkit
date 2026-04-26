import sys
import os
import json
import re
from youtube_transcript_api import YouTubeTranscriptApi

def get_video_id(url_or_id):
    # Regex to extract video ID from various YouTube URL formats
    pattern = r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url_or_id)
    if match:
        return match.group(1)
    # If no match, check if it's already an 11-char ID
    if len(url_or_id) == 11:
        return url_or_id
    return None

def log_failure(action_name, video_id, url, query, reason):
    try:
        from pathlib import Path
        import importlib.util
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        log_script = os.path.join(skills_dir, "unf", "scripts", "log_provenance.py")
        if os.path.exists(log_script):
            spec = importlib.util.spec_from_file_location("log_provenance", log_script)
            log_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(log_module)
            inputs = [{"@type": "sc:URL", "url": url, "name": video_id}]
            log_module.log_action(action_name, inputs, [], script_path=os.path.abspath(__file__), query=query, status="Failed")
    except Exception:
        pass

def transcribe_video(video_id, output_dir, target_url, cookies_path=None, query=None):
    from requests import Session
    import http.cookiejar

    print(f"Attempting to transcribe video: {video_id}")
    # Initialize a shared session with browser headers
    session = Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/'
    })

    try:
        # Load cookies into the session if provided
        if cookies_path and os.path.exists(cookies_path):
            cj = http.cookiejar.MozillaCookieJar(cookies_path)
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj
            print(f"Using cookies from: {cookies_path}")
        
        # Initialize the API with our authenticated session
        api = YouTubeTranscriptApi(http_client=session)
        
        # Fetch the transcript list
        transcript_list_obj = api.list(video_id)
        
        try:
            transcript_data = transcript_list_obj.find_transcript(['en', 'en-US', 'ru']).fetch()
        except:
            transcript_data = transcript_list_obj.find_generated_transcript(['en', 'ru']).fetch()

        full_text = " ".join([item.text for item in transcript_data])
        
        output_path = os.path.join(output_dir, f"{video_id}.txt")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
            
        print(f"Successfully saved transcript to {output_path}")

        # --- Fingerprinting (Provenance) ---
        transcript_unf = None
        command_unf = None
        try:
            # Dynamically resolve the relative path of this script from the project root
            script_path_abs = os.path.abspath(__file__)
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))))
            
            # Dynamically locate the UNF skill
            unf_script_path = os.path.join(root_dir, ".gemini", "skills", "unf", "scripts", "unf_hash.py")
            if os.path.exists(unf_script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("unf_hash", unf_script_path)
                unf_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(unf_module)
                
                # 1. Fingerprint the transcript CONTENT
                transcript_unf = unf_module.compute_unf_string(full_text)
                if transcript_unf:
                    transcript_unf = transcript_unf.replace("UNF:6:", "UNF6:")
                    print(f"Transcript Fingerprint: {transcript_unf}")

                # 2. Fingerprint the COMMAND invocation (for provenance)
                script_path_abs = os.path.abspath(__file__)
                script_rel_path = os.path.relpath(script_path_abs, root_dir)
                command_string = f"{script_rel_path} {target_url}"
                command_unf = unf_module.compute_unf_string(command_string)
                if command_unf:
                    command_unf = command_unf.replace("UNF:6:", "UNF6:")
                    print(f"Command Signature: {command_unf}")
        except Exception as unf_err:
            print(f"Warning: Fingerprinting failed: {unf_err}")

        # Use the SAME session to fetch metadata immediately
        try:
            from get_metadata import fetch_metadata
            print("Fetching metadata with shared session and transcript...")
            metadata = fetch_metadata(video_id, session=session, transcript_text=full_text, unf_hash=command_unf, transcript_unf=transcript_unf)
            if metadata:
                # Add query to metadata for traceability
                if query:
                    metadata["userQuery"] = query

                meta_dir = os.path.join(os.environ.get("DATA_ROOT", "data"), "metadata")
                os.makedirs(meta_dir, exist_ok=True)
                meta_path = os.path.join(meta_dir, f"{video_id}.json")
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=4, ensure_ascii=False)
                print(f"Successfully saved metadata to {meta_path}")

                # --- Note: Croissant Serialization is now handled by a separate expert ---
                print(f"Successfully saved metadata to {meta_path}")

                        # --- Provenance Graph Logging ---
                        try:
                            log_script_path = os.path.join(root_dir, ".gemini", "skills", "unf", "scripts", "log_provenance.py")
                            if os.path.exists(log_script_path):
                                spec = importlib.util.spec_from_file_location("log_provenance", log_script_path)
                                log_module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(log_module)
                                
                                inputs = [{"@type": "URL", "url": target_url, "identifier": command_unf}]
                                outputs = [
                                    {"@type": "FileObject", "name": f"{video_id}.txt", "unf": transcript_unf},
                                    {"@type": "FileObject", "name": f"{video_id}.json", "unf": metadata.get("unf")}
                                ]
                                log_module.log_action("transcribe_and_serialize", inputs, outputs, script_path=script_path_abs, query=query, status="Completed")
                        except Exception as log_err:
                            print(f"Warning: Provenance logging failed: {log_err}")
                except Exception as croissant_err:
                    print(f"Warning: Croissant serialization failed: {croissant_err}")
                    log_failure("transcribe_and_serialize", video_id, target_url, query, str(croissant_err))
        except ImportError:
            pass
            
        return True
    except Exception as e:
        print(f"Error transcribing {video_id}: {e}")
        log_failure("transcribe_and_serialize", video_id, target_url, query, str(e))
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Transcriber with Metadata Support")
    parser.add_argument('target', nargs='?', help='Video ID or URL')
    parser.add_argument('--cookies', help='Path to cookies.txt file in Netscape format')
    parser.add_argument('--query', help='Original user query for traceability')
    
    args = parser.parse_args()
    
    cookies = args.cookies
    target = args.target
    query = args.query

    # Add script directory to path for imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.append(script_dir)

    # Auto-resolve DATA_ROOT if query is provided and not already set
    if query and not os.environ.get("DATA_ROOT"):
        try:
            skills_dir = os.path.dirname(os.path.dirname(script_dir))
            unf_script = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
            if os.path.exists(unf_script):
                import importlib.util
                spec = importlib.util.spec_from_file_location("unf_hash", unf_script)
                unf_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(unf_mod)
                os.environ["DATA_ROOT"] = unf_mod.get_partitioned_root(query)
        except Exception:
            pass

    output_dir = os.path.join(os.environ.get("DATA_ROOT", "data"), "transcripts")
    os.makedirs(output_dir, exist_ok=True)

    if not target:
        if os.path.exists('youtube_search_results.json'):
            print("No arguments provided. Detecting batch mode...")
            with open('youtube_search_results.json', 'r') as f:
                results = json.load(f)
            
            count = 0
            for item in results:
                vid = item.get('id')
                url = item.get('url') or f"https://www.youtube.com/watch?v={vid}"
                if vid and transcribe_video(vid, output_dir, url, cookies, query=query):
                    count += 1
            
            print(f"\nBatch process complete. {count} items processed.")
            return

        print("Usage: python3 transcribe.py <VIDEO_ID_OR_URL> [--cookies cookies.txt]")
        sys.exit(1)
        
    video_id = get_video_id(target)
    if not video_id:
        print(f"Invalid Video ID or URL: {target}")
        sys.exit(1)
    
    # Use full URL if provided, otherwise reconstruct it for the signature
    url = target if target.startswith("http") else f"https://www.youtube.com/watch?v={video_id}"
        
    # output_dir is already defined at line 190
    transcribe_video(video_id, output_dir, url, cookies, query=query)

if __name__ == "__main__":
    main()

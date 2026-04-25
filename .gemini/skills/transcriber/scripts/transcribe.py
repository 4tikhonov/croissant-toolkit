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

def transcribe_video(video_id, output_dir, cookies_path=None):
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
        
        # Use the SAME session to fetch metadata immediately
        # This keeps the authenticated context alive
        try:
            from get_metadata import fetch_metadata
            print("Fetching metadata with shared session...")
            metadata = fetch_metadata(video_id, session=session)
            if metadata:
                meta_dir = "data/metadata"
                os.makedirs(meta_dir, exist_ok=True)
                meta_path = os.path.join(meta_dir, f"{video_id}.json")
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=4, ensure_ascii=False)
                print(f"Successfully saved metadata to {meta_path}")
        except ImportError:
            # Fallback if import fails (e.g. running outside the scripts dir)
            pass
            
        return True
    except Exception as e:
        print(f"Error transcribing {video_id}: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Transcriber with Metadata Support")
    parser.add_argument('target', nargs='?', help='Video ID or URL')
    parser.add_argument('--cookies', help='Path to cookies.txt file in Netscape format')
    
    args = parser.parse_args()
    
    cookies = args.cookies
    target = args.target

    # Add script directory to path for imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.append(script_dir)

    if not target:
        if os.path.exists('youtube_search_results.json'):
            print("No arguments provided. Detecting batch mode...")
            with open('youtube_search_results.json', 'r') as f:
                results = json.load(f)
            
            output_dir = "data/transcripts"
            os.makedirs(output_dir, exist_ok=True)
            
            count = 0
            for item in results:
                vid = item.get('id')
                if vid and transcribe_video(vid, output_dir, cookies):
                    count += 1
            
            print(f"\nBatch process complete. {count} items processed.")
            return

        print("Usage: python3 transcribe.py <VIDEO_ID_OR_URL> [--cookies cookies.txt]")
        sys.exit(1)
        
    video_id = get_video_id(target)
    if not video_id:
        print(f"Invalid Video ID or URL: {target}")
        sys.exit(1)
        
    output_dir = "data/transcripts"
    os.makedirs(output_dir, exist_ok=True)
    
    transcribe_video(video_id, output_dir, cookies)

if __name__ == "__main__":
    main()

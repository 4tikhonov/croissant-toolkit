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

def transcribe_video(video_id, output_dir):
    print(f"Attempting to transcribe video: {video_id}")
    try:
        # Initialize the API instance
        api = YouTubeTranscriptApi()
        
        # Fetch the transcript list
        transcript_list_obj = api.list(video_id)
        
        # Try to find a manually created or generated transcript in English or Russian
        try:
            transcript_data = transcript_list_obj.find_transcript(['en', 'en-US', 'ru']).fetch()
        except:
            # Fallback to any available transcript if preferred languages are not found exactly
            transcript_data = transcript_list_obj.find_generated_transcript(['en', 'ru']).fetch()

        # Combine the text
        full_text = " ".join([item.text for item in transcript_data])
        
        # Save to file
        output_path = os.path.join(output_dir, f"{video_id}.txt")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
            
        print(f"Successfully saved transcript to {output_path}")
        return True
    except Exception as e:
        print(f"Error transcribing {video_id}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        # Check if youtube_search_results.json exists as a fallback
        if os.path.exists('youtube_search_results.json'):
            print("No arguments provided. Detecting batch mode from youtube_search_results.json...")
            with open('youtube_search_results.json', 'r') as f:
                results = json.load(f)
            
            output_dir = "data/transcripts"
            os.makedirs(output_dir, exist_ok=True)
            
            count = 0
            script_dir = os.path.dirname(os.path.abspath(__file__))
            metadata_script = os.path.join(script_dir, "get_metadata.py")
            
            for item in results:
                vid = item.get('id')
                if vid and transcribe_video(vid, output_dir):
                    count += 1
                    if os.path.exists(metadata_script):
                        subprocess.run([sys.executable, metadata_script, vid])
            
            print(f"\nBatch process complete. {count} transcripts and metadata collected.")
            return

        print("Usage: python3 transcribe.py <VIDEO_ID_OR_URL>")
        sys.exit(1)
        
    target = sys.argv[1]
    video_id = get_video_id(target)
    
    if not video_id:
        print(f"Invalid Video ID or URL: {target}")
        sys.exit(1)
        
    output_dir = "data/transcripts"
    os.makedirs(output_dir, exist_ok=True)
    
    if transcribe_video(video_id, output_dir):
        # Extend: Fetch metadata automatically
        print("\nFetching metadata...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        metadata_script = os.path.join(script_dir, "get_metadata.py")
        if os.path.exists(metadata_script):
            subprocess.run([sys.executable, metadata_script, video_id])

if __name__ == "__main__":
    import subprocess
    main()

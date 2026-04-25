import sys
import os
import json
import re
import urllib.request
import urllib.parse

def get_video_id(url_or_id):
    pattern = r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url_or_id)
    if match: return match.group(1)
    if len(url_or_id) == 11: return url_or_id
    return None

def fetch_metadata(video_id, session=None):
    from requests import Session
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # If no session provided, create a basic one with headers
    if session is None:
        session = Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/'
        })
    
    try:
        response = session.get(url)
        response.raise_for_status()
        html = response.text
            
        # 1. Extract JSON-LD (Schema.org)
        json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        schema_data = {}
        if json_ld_match:
            try:
                schema_data = json.loads(json_ld_match.group(1))
            except:
                pass

        # 2. Extract ytInitialData
        initial_data_match = re.search(r'var ytInitialData = (\{.*?\});', html)
        initial_data = {}
        if initial_data_match:
            try:
                initial_data = json.loads(initial_data_match.group(1))
            except:
                pass

        # 3. Extract ytInitialPlayerResponse for metadata fallback
        player_response_match = re.search(r'var ytInitialPlayerResponse = (\{.*?\});', html)
        player_response = {}
        if player_response_match:
            try:
                player_response = json.loads(player_response_match.group(1))
            except:
                pass

        # Parse fields
        title = schema_data.get('name')
        if not title and initial_data:
            try:
                title = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['title']['runs'][0]['text']
            except:
                pass
        if not title and player_response:
            title = player_response.get('videoDetails', {}).get('title')

        description = schema_data.get('description')
        if not description and initial_data:
            try:
                contents = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
                for c in contents:
                    if 'videoSecondaryInfoRenderer' in c:
                        desc_runs = c['videoSecondaryInfoRenderer']['description']['runs']
                        description = "".join([r['text'] for r in desc_runs])
            except:
                pass
        if not description and player_response:
            description = player_response.get('videoDetails', {}).get('shortDescription')

        # Author and Channel info
        author_name = None
        channel_id = None
        
        # Try Schema first
        if 'author' in schema_data:
            author_data = schema_data['author']
            if isinstance(author_data, dict):
                author_name = author_data.get('name')
            elif isinstance(author_data, str):
                author_name = author_data
        
        # Fallback to Player Response
        if not author_name and player_response:
            author_name = player_response.get('videoDetails', {}).get('author')
            channel_id = player_response.get('videoDetails', {}).get('channelId')
            
        # Fallback to Initial Data
        if not author_name and initial_data:
            try:
                contents = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
                for c in contents:
                    if 'videoSecondaryInfoRenderer' in c:
                        owner = c['videoSecondaryInfoRenderer']['owner']['videoOwnerRenderer']
                        author_name = owner['title']['runs'][0]['text']
                        # Extract channel ID from navigationEndpoint if possible
                        try:
                            channel_id = owner['title']['runs'][0]['navigationEndpoint']['browseEndpoint']['browseId']
                        except:
                            pass
            except:
                pass

        views = schema_data.get('interactionCount')
        if not views and initial_data:
            try:
                contents = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
                for c in contents:
                    if 'videoPrimaryInfoRenderer' in c:
                        views_text = c['videoPrimaryInfoRenderer']['viewCount']['videoViewCountRenderer']['viewCount']['simpleText']
                        views = re.sub(r'[^\d]', '', views_text)
            except:
                pass

        metadata = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": title or "Unknown Title",
            "description": description or "",
            "url": url,
            "author": {
                "@type": "Person",
                "name": author_name or "Unknown Channel",
                "url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
            },
            "publisher": {
                "@type": "Organization",
                "name": author_name or "YouTube",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://www.youtube.com/img/desktop/yt_1200.png"
                }
            },
            "interactionCount": views or "0",
            "commentCount": schema_data.get('commentCount') or "0",
            "identifier": video_id,
            "uploadDate": schema_data.get('uploadDate')
        }
        
        return metadata
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 get_metadata.py <VIDEO_ID_OR_URL>")
        sys.exit(1)
        
    target = sys.argv[1]
    video_id = get_video_id(target)
    
    if not video_id:
        print(f"Invalid Video ID or URL: {target}")
        sys.exit(1)
        
    output_dir = "data/metadata"
    os.makedirs(output_dir, exist_ok=True)
    
    metadata = fetch_metadata(video_id)
    if metadata:
        output_path = os.path.join(output_dir, f"{video_id}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved metadata to {output_path}")
        print(json.dumps(metadata, indent=4))
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

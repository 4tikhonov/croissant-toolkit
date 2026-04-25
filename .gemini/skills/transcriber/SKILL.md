---
name: transcriber
description: Fetch and store transcripts from YouTube videos for deep content analysis.
---

# Transcriber Skill

The Transcriber skill allows the agent to download the text transcript (closed captions) of YouTube videos. This is essential for converting video tutorials and discussions into searchable and indexable text for the Croissant metadata engine.

Transcripts are stored locally in `./data/transcripts/` as plain text files named by their YouTube Video ID.

## Tools

### 1. Transcribe YouTube Video
Fetches the transcript for a single video ID/URL or automatically processes the `youtube_search_results.json` if no arguments are provided.

**Usage:**
```bash
# Transcribe a specific video
python3 transcriber/scripts/transcribe.py <VIDEO_URL_OR_ID>

# Batch transcribe the results from the last Youtuber search
python3 transcriber/scripts/transcribe.py
```

### 2. Fetch Video Metadata
Extracts high-fidelity metadata (Title, Description, Views, Upload Date) in Schema.org JSON-LD format.

**Usage:**
```bash
python3 transcriber/scripts/get_metadata.py <VIDEO_URL_OR_ID>
```

**Output:**
Metadata is saved to `./data/metadata/<VIDEO_ID>.json`.

**Example:**
`python3 transcriber/scripts/transcribe.py https://www.youtube.com/watch?v=6cWcZ2G53gE`

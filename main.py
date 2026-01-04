import os
import json
import requests
import time
import sys
import re
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# --- Configuration ---
URLS = [
    "https://evilgodfahim.github.io/sci/daily_feed.xml",
    "https://evilgodfahim.github.io/fp/final.xml",
    "https://evilgodfahim.github.io/bdl/final.xml",
    "https://evilgodfahim.github.io/int/final.xml",
    "https://evilgodfahim.github.io/gpd/daily_feed.xml",
    "https://evilgodfahim.github.io/daily/daily_master.xml",
    "https://evilgodfahim.github.io/bdit/daily_feed_2.xml",
    "https://evilgodfahim.github.io/bdit/daily_feed.xml",
    "https://evilgodfahim.github.io/edit/daily_feed.xml"
]

# Optimized Configuration - Lower batch sizes for reliability
MODELS = [
    {"name": "llama-3.3-70b-versatile", "display": "Llama-3.3-70B", "batch_size": 50}, # Reduced from 150 to prevent JSON cutoffs
    {"name": "qwen-2.5-32b", "display": "Qwen-2.5-32B", "batch_size": 40},             # Switched to stable Qwen 2.5
    {"name": "mixtral-8x7b-32768", "display": "Mixtral-8x7b", "batch_size": 50}        # Fallback efficient model
]
# Note: Ensure GROQ_API_KEY is set in your environment variables
GROQ_API_KEY = os.environ.get("GEM")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a Chief Information Filter.
Your task is to select headlines with structural and lasting significance.
OUTPUT SPEC (strict):
Return ONLY a valid JSON array. Do not write "Here is the JSON" or any intro text.
Format: [{"id": 123, "category": "POWER RELATIONS", "reason": "Explains systemic change."}]
"""

FULL_SYSTEM_PROMPT = """You are a Chief Information Filter.
Your task is to select headlines with structural and lasting significance.
You do not evaluate importance by popularity, novelty, or emotion.
You evaluate how information explains or alters systems.

TWO INFORMATION TYPES:
1. STRUCTURAL (Select these): Explains how power, institutions, or economies operate/change.
2. EPISODIC (Ignore these): Isolated events, crime, sports, individual actions.

OUTPUT SPEC:
Return ONLY a JSON array. 
Each item must contain exactly: 
- id (integer from input)
- category (Governance, Economics, Power Relations, or Ideas)
- reason (one concise sentence)

Start with [ and end with ]. No markdown formatting.
"""

def save_xml(data, error_message=None):
    filename = "filtered_feed.xml"
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Elite News Feed - 3-Model Ensemble"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    ET.SubElement(channel, "link").text = "https://github.com/evilgodfahim"
    ET.SubElement(channel, "description").text = "AI-curated feed using Llama, Qwen, and Mixtral ensemble"

    if error_message:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "System Error"
        ET.SubElement(item, "description").text = f"Script failed: {error_message}"
        ET.SubElement(item, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    elif not data:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "System Running - No Priority News"
        ET.SubElement(item, "description").text = "No structurally significant articles found in the last 26 hours."
        ET.SubElement(item, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    else:
        for art in data:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = art['title']
            ET.SubElement(item, "link").text = art['link']
            ET.SubElement(item, "pubDate").text = art['pubDate']
            
            models_str = ", ".join(art.get('selected_by', ['Unknown']))
            category_info = art.get('category', 'News')
            reason_info = art.get('reason', 'Selected')
            
            html_desc = f"<p><b>[{category_info}]</b></p>"
            html_desc += f"<p><i>{reason_info}</i></p>"
            html_desc += f"<p><small>Selected by: {models_str}</small></p>"
            html_desc += f"<hr/><p>{art['description']}</p>"
            
            ET.SubElement(item, "description").text = html_desc

    try:
        tree = ET.ElementTree(rss)
        ET.indent(tree, space="  ", level=0)
        tree.write(filename, encoding="utf-8", xml_declaration=True)
        print(f"\nSuccessfully saved {len(data) if data else 0} items to {filename}", flush=True)
    except Exception as e:
        print(f"::error::Failed to write XML: {e}", flush=True)

def fetch_titles_only():
    all_articles = []
    seen_links = set()
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=26)
    
    print(f"Time Filter: Articles after {cutoff_time.strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
    headers = {'User-Agent': 'BCS-Curator/3.0-Ensemble'}

    for url in URLS:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200: continue
            
            try:
                root = ET.fromstring(r.content)
            except: continue

            for item in root.findall('.//item'):
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                if not pub_date: continue
                
                try:
                    dt = parsedate_to_datetime(pub_date)
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                    else: dt = dt.astimezone(timezone.utc)
                    if dt < cutoff_time: continue
                except: continue

                link = item.find('link').text or ""
                if not link or link in seen_links: continue
                
                title = item.find('title').text or "No Title"
                title = title.strip()
                seen_links.add(link)
                
                desc = item.find('description')
                desc_text = desc.text if desc is not None else ""

                all_articles.append({
                    "id": len(all_articles),
                    "title": title,
                    "link": link,
                    "description": desc_text or title,
                    "pubDate": pub_date
                })
        except Exception: continue

    print(f"Loaded {len(all_articles)} unique headlines", flush=True)
    return all_articles

def extract_json_from_text(text):
    """
    Robustly extracts JSON array from text even if the model adds conversational filler.
    """
    try:
        # Attempt 1: Direct parse
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        # Attempt 2: Find the first '[' and the last ']'
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
        
    return None

def call_model(model_info, batch):
    prompt_list = [f"{a['id']}: {a['title']}" for a in batch]
    prompt_text = "\n".join(prompt_list)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_info["name"],
        "messages": [
            {"role": "system", "content": FULL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the headlines to filter:\n{prompt_text}"}
        ],
        "temperature": 0.1, # Keep strictly deterministic
        "max_tokens": 4096
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=90)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # CLEANUP: Remove code blocks if present
                if content.startswith("```"):
                    content = content.replace("```json", "").replace("```", "").strip()

                parsed_data = extract_json_from_text(content)
                
                if parsed_data is not None and isinstance(parsed_data, list):
                    return parsed_data
                else:
                    print(f"    [{model_info['display']}] JSON format error (Attempt {attempt+1})", flush=True)
                    # Debug: Print first 50 chars to see what went wrong
                    # print(f"DEBUG CONTENT: {content[:50]}...") 
                    if attempt < max_retries - 1: time.sleep(2)
                    continue

            elif response.status_code == 429:
                wait_time = 40 * (attempt + 1) # Aggressive wait: 40s, 80s, 120s
                print(f"    [{model_info['display']}] Rate limit (429) - Waiting {wait_time}s...", flush=True)
                time.sleep(wait_time)
                continue
            
            elif response.status_code >= 500:
                print(f"    [{model_info['display']}] Server Error {response.status_code} - Retrying...", flush=True)
                time.sleep(5)
                continue
            
            else:
                print(f"    [{model_info['display']}] API Error {response.status_code}", flush=True)
                return []

        except requests.exceptions.RequestException as e:
            print(f"    [{model_info['display']}] Network Error: {str(e)[:50]}", flush=True)
            time.sleep(5)
    
    return []

# --- Similarity / Dedup helpers ---
def extract_key_terms(text):
    bangla_stops = {'এ', 'এর', 'ও', 'তে', 'না', 'কে', 'যে', 'হয়', 'এবং', 'করে', 'থেকে'}
    english_stops = {'the', 'a', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are'}
    words = re.split(r'\s+', text.lower())
    all_stops = bangla_stops | english_stops
    return {w for w in words if len(w) > 2 and w not in all_stops}

def fast_similarity(terms1, terms2):
    if not terms1 or not terms2: return 0.0
    intersection = len(terms1 & terms2)
    union = len(terms1 | terms2)
    return intersection / union if union else 0.0

def semantic_deduplication(articles, similarity_threshold=0.6):
    if not articles or len(articles) < 2: return articles
    print(f"\nSemantic deduplication (threshold={similarity_threshold})...", flush=True)
    
    article_terms = [extract_key_terms(art['title']) for art in articles]
    keep = [True] * len(articles)
    duplicates = 0
    
    for i in range(len(articles)):
        if not keep[i]: continue
        for j in range(i + 1, len(articles)):
            if not keep[j]: continue
            
            if fast_similarity(article_terms[i], article_terms[j]) >= similarity_threshold:
                # Keep the one with longer description
                if len(articles[j].get('description', '')) > len(articles[i].get('description', '')):
                    keep[i] = False
                    duplicates += 1
                    break 
                else:
                    keep[j] = False
                    duplicates += 1
    
    result = [articles[i] for i in range(len(articles)) if keep[i]]
    print(f"   Removed {duplicates} semantic duplicates", flush=True)
    return result

def main():
    print("=" * 60, flush=True)
    print("Elite News Curator - 3-Model Ensemble (Optimized)", flush=True)
    print("=" * 60, flush=True)

    if not GROQ_API_KEY:
        print("::error::GEM environment variable (API Key) is missing!", flush=True)
        sys.exit(1)
    
    articles = fetch_titles_only()
    if not articles:
        print("No articles found.", flush=True)
        save_xml([])
        return

    # Process batches
    model_batches = {}
    for model_info in MODELS:
        bs = model_info['batch_size']
        model_batches[model_info['name']] = [articles[i:i + bs] for i in range(0, len(articles), bs)]
    
    max_batch_count = max(len(batches) for batches in model_batches.values())
    MAX_BATCHES_LIMIT = 15 # Safety limit
    
    selections_map = {}
    
    print(f"\nProcessing batches (Max {min(max_batch_count, MAX_BATCHES_LIMIT)} groups)...", flush=True)

    for batch_idx in range(min(MAX_BATCHES_LIMIT, max_batch_count)):
        print(f"  Batch Group {batch_idx+1}...", flush=True)
        
        for model_info in MODELS:
            m_name = model_info['name']
            if batch_idx >= len(model_batches[m_name]): continue
            
            batch = model_batches[m_name][batch_idx]
            decisions = call_model(model_info, batch)
            
            if decisions:
                print(f"    [{model_info['display']}] Selected {len(decisions)} articles", flush=True)
                for d in decisions:
                    aid = d.get('id')
                    if aid is not None and isinstance(aid, int) and aid < len(articles):
                        if aid not in selections_map:
                            selections_map[aid] = {'models': [], 'decisions': []}
                        selections_map[aid]['models'].append(model_info['display'])
                        selections_map[aid]['decisions'].append(d)
            else:
                 print(f"    [{model_info['display']}] No selections or error", flush=True)

            # Essential delay to avoid rate limits
            time.sleep(5) 
        
        print("    Cooling down (10s)...", flush=True)
        time.sleep(10)

    # Merging
    final_articles = []
    seen_ids = set()
    
    print(f"\nMerging selections...", flush=True)
    for aid, info in selections_map.items():
        original = articles[aid].copy()
        
        # Use info from the first model that selected it
        first_dec = info['decisions'][0]
        original['category'] = first_dec.get('category', 'Priority')
        original['reason'] = first_dec.get('reason', 'Systemic Significance')
        original['selected_by'] = info['models']
        
        final_articles.append(original)

    # Deduplication
    final_articles = semantic_deduplication(final_articles)
    
    # Stats
    print(f"\nRESULTS:", flush=True)
    print(f"   Analyzed: {len(articles)} headlines", flush=True)
    print(f"   Selected: {len(final_articles)} unique articles", flush=True)
    
    save_xml(final_articles)

if __name__ == "__main__":
    main()

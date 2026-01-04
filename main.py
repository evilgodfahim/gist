import os
import json
import requests
import time
import sys
import re
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import defaultdict

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

# YOUR ORIGINAL MODELS
# Note: Batch sizes lowered to 50 to fix the "413 Payload Too Large" and JSON errors
MODELS = [
    {"name": "llama-3.3-70b-versatile", "display": "Llama-3.3-70B", "batch_size": 50},
    {"name": "qwen/qwen3-32b", "display": "Qwen-3-32B", "batch_size": 50},
    {"name": "openai/gpt-oss-120b", "display": "GPT-OSS-120B", "batch_size": 50}
]

GROQ_API_KEY = os.environ.get("GEM")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# YOUR EXACT ORIGINAL PROMPT
SYSTEM_PROMPT = """You are a Chief Information Filter.
Your task is to select headlines with structural and lasting significance.
You do not evaluate importance by popularity, novelty, or emotion.
You evaluate how information explains or alters systems.
Judgment must rely only on linguistic structure, implied scope, and systemic consequence.
TWO INFORMATION TYPES (internal use)
STRUCTURAL
— Explains how power, institutions, economies, or long-term social/strategic forces operate or change.
EPISODIC
— Describes isolated events, individual actions, or short-lived situations without system impact.
Select only STRUCTURAL.
FOUR STRUCTURAL LENSES (exclusive)
GOVERNANCE & CONTROL
Rules, enforcement, institutional balance, authority transfer, administrative or judicial change.
ECONOMIC & RESOURCE FLOWS
Capital movement, trade structure, production capacity, fiscal or monetary direction, systemic risk.
POWER RELATIONS & STRATEGY
Strategic alignment, coercion, deterrence, security posture, long-term rivalry or cooperation.
IDEAS, ARGUMENTS & LONG-TERM TRENDS
Editorial reasoning, policy debate, scientific or technological trajectories, demographic or climate forces.
CONTEXTUAL GRAVITY RULE (KEY)
When two or more headlines show equal structural strength, favor the one that:
• Operates closer to the decision-making center of a society
• Directly affects national policy formation or institutional practice
• Originates from internal analytical or editorial discourse, not external observation
This rule applies universally, regardless of language or country.
SINGLE DECISION TEST (mandatory)
Ask only:
"Does this headline clarify how a system functions or how its future direction is being shaped, in a way that remains relevant after time passes?"
• Yes or plausibly yes → SELECT
• No → SKIP
No secondary tests.
AUTOMATIC EXCLUSIONS
Skip always: • Crime, accidents, or scandals without institutional consequence
• Sports, entertainment, lifestyle
• Personal narratives without systemic implication
• Repetition of already-settled facts
OUTPUT SPEC (strict)
Return only a JSON array.
Each item must contain exactly: id
category (one of the four lenses)
reason (one concise sentence explaining the structural significance)
No markdown.
No commentary.
No text outside JSON.
Start with [ and end with ]."""

def save_xml(data, error_message=None):
    filename = "filtered_feed.xml"
    
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Elite News Feed - 3-Model Ensemble"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    ET.SubElement(channel, "link").text = "https://github.com/evilgodfahim"
    ET.SubElement(channel, "description").text = "AI-curated feed using Llama, Qwen, and GPT ensemble"

    if error_message:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "System Error"
        ET.SubElement(item, "description").text = f"Script failed: {error_message}"
        ET.SubElement(item, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
        ET.SubElement(item, "link").text = "https://github.com/evilgodfahim"
    
    elif not data:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "System Running - No Priority News Today"
        ET.SubElement(item, "description").text = "Curation system working. No structurally significant articles found in the last 26 hours."
        ET.SubElement(item, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
        ET.SubElement(item, "link").text = "https://github.com/evilgodfahim"
        
    else:
        for art in data:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = art['title']
            ET.SubElement(item, "link").text = art['link']
            ET.SubElement(item, "pubDate").text = art['pubDate']
            
            # Build description with model attribution
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
        print(f"\nSuccessfully saved {len(data) if data else 0} priority items to {filename}", flush=True)
        
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"File created: {filename} ({file_size} bytes)", flush=True)
            
    except Exception as e:
        print(f"::error::Failed to write XML: {e}", flush=True)

def fetch_titles_only():
    all_articles = []
    seen_links = set()
    seen_titles = set()
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=26)
    
    print(f"Time Filter: Articles after {cutoff_time.strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
    headers = {'User-Agent': 'BCS-Curator/3.0-Ensemble'}

    for url in URLS:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200: 
                continue
            
            try:
                root = ET.fromstring(r.content)
            except: 
                continue

            for item in root.findall('.//item'):
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                if not pub_date: 
                    continue
                
                try:
                    dt = parsedate_to_datetime(pub_date)
                    if dt.tzinfo is None: 
                        dt = dt.replace(tzinfo=timezone.utc)
                    else: 
                        dt = dt.astimezone(timezone.utc)
                    if dt < cutoff_time: 
                        continue
                except: 
                    continue

                link = item.find('link').text or ""
                if not link or link in seen_links: 
                    continue
                
                title = item.find('title').text or "No Title"
                title = title.strip()
                
                title_normalized = title.lower().strip()
                if title_normalized in seen_titles:
                    continue
                
                seen_links.add(link)
                seen_titles.add(title_normalized)
                
                desc = item.find('description')
                desc_text = desc.text if desc is not None else ""

                all_articles.append({
                    "id": len(all_articles),
                    "title": title,
                    "link": link,
                    "description": desc_text or title,
                    "pubDate": pub_date
                })

        except Exception:
            continue

    print(f"Loaded {len(all_articles)} unique headlines (deduped)", flush=True)
    return all_articles

def extract_key_terms(text):
    bangla_stops = {'এ', 'এর', 'ও', 'তে', 'না', 'কে', 'যে', 'হয়', 'এবং', 'করে', 'থেকে'}
    english_stops = {'the', 'a', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are'}
    words = re.split(r'\s+', text.lower())
    all_stops = bangla_stops | english_stops
    return {w for w in words if len(w) > 2 and w not in all_stops}

def fast_similarity(terms1, terms2):
    if not terms1 or not terms2:
        return 0.0
    intersection_size = len(terms1 & terms2)
    union_size = len(terms1 | terms2)
    return intersection_size / union_size if union_size else 0.0

def semantic_deduplication(articles, similarity_threshold=0.6):
    if not articles or len(articles) < 2:
        return articles
    
    print(f"\nSemantic deduplication (threshold={similarity_threshold})...", flush=True)
    article_terms = [extract_key_terms(art['title']) for art in articles]
    keep = [True] * len(articles)
    duplicates = 0
    
    for i in range(len(articles)):
        if not keep[i]: continue
        for j in range(i + 1, len(articles)):
            if not keep[j]: continue
            
            sim = fast_similarity(article_terms[i], article_terms[j])
            
            if sim >= similarity_threshold:
                len_i = len(articles[i].get('description', ''))
                len_j = len(articles[j].get('description', ''))
                
                if len_j > len_i:
                    keep[i] = False
                    duplicates += 1
                    break 
                else:
                    keep[j] = False
                    duplicates += 1
    
    result = [articles[i] for i in range(len(articles)) if keep[i]]
    print(f"   Removed {duplicates} semantic duplicates", flush=True)
    return result

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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=90)
            
            # --- 429 RATE LIMIT HANDLING ---
            if response.status_code == 429:
                wait_time = 40 * (attempt + 1)
                print(f"    [{model_info['display']}] Rate limit (429) - waiting {wait_time}s...", flush=True)
                time.sleep(wait_time)
                continue

            # --- 413 PAYLOAD HANDLING ---
            if response.status_code == 413:
                print(f"    [{model_info['display']}] Batch too large (413).", flush=True)
                return [] 
            
            # --- SUCCESS CASE ---
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # --- FIX 1: Robust Regex Extraction ---
                # This fixes the "JSON parse error" by finding the array boundaries
                try:
                    match = re.search(r'(\[.*\])', content, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        parsed = json.loads(json_str)
                    else:
                        # Fallback to direct load
                        parsed = json.loads(content)
                        
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict) and 'results' in parsed:
                        return parsed['results']
                    
                except json.JSONDecodeError:
                    print(f"    [{model_info['display']}] JSON parse error (attempt {attempt+1})", flush=True)
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return []
            
            # --- SERVER ERROR ---
            elif response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
                return []

        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return []
            
        except Exception as e:
            print(f"    [{model_info['display']}] Error: {str(e)[:60]}", flush=True)
            return []
    
    return []

def main():
    print("=" * 70, flush=True)
    print("Elite News Curator - 3-Model Ensemble", flush=True)
    print("=" * 70, flush=True)
    
    if not GROQ_API_KEY:
        print("::error::GEM environment variable is missing!", flush=True)
        sys.exit(1)

    if not os.path.exists("filtered_feed.xml"):
        print("First run detected - creating initial XML file...", flush=True)
        save_xml([], error_message=None)
    
    try:
        articles = fetch_titles_only()
        
        if not articles:
            print("No articles found in source feeds", flush=True)
            save_xml([])
            print("\nScript completed successfully (no articles to process)", flush=True)
            return

        # Create model-specific batches
        model_batches = {}
        for model_info in MODELS:
            batch_size = model_info['batch_size']
            model_batches[model_info['name']] = [
                articles[i:i + batch_size] for i in range(0, len(articles), batch_size)
            ]
        
        max_batch_count = max(len(batches) for batches in model_batches.values())
        MAX_BATCHES = 15
        
        selections_map = {}
        
        print(f"\nProcessing articles with 3-model ensemble...", flush=True)

        batches_processed = 0
        
        for batch_idx in range(min(MAX_BATCHES, max_batch_count)):
            print(f"  Batch Group {batch_idx+1}...", flush=True)
            
            for model_info in MODELS:
                model_name = model_info['name']
                model_batches_list = model_batches[model_name]
                
                if batch_idx >= len(model_batches_list):
                    continue
                
                batch = model_batches_list[batch_idx]
                
                decisions = call_model(model_info, batch)
                
                if decisions:
                    print(f"    [{model_info['display']}] Selected {len(decisions)} articles", flush=True)
                    for d in decisions:
                        article_id = d.get('id')
                        if article_id is not None and isinstance(article_id, int) and article_id < len(articles):
                            if article_id not in selections_map:
                                selections_map[article_id] = {
                                    'models': [],
                                    'decisions': []
                                }
                            selections_map[article_id]['models'].append(model_info['display'])
                            selections_map[article_id]['decisions'].append(d)
                else:
                    print(f"    [{model_info['display']}] No selections", flush=True)
                
                time.sleep(5)
            
            batches_processed += 1
            
            if batch_idx < min(MAX_BATCHES, max_batch_count) - 1:
                print(f"    Batch group complete. Waiting 10 seconds...\n", flush=True)
                time.sleep(10)

        # Build final article list with deduplication
        final_articles = []
        seen_links = set()
        seen_titles = set()
        
        print(f"\nMerging selections from all models...", flush=True)
        
        for article_id, selection_info in selections_map.items():
            original = next((x for x in articles if x["id"] == article_id), None)
            if not original:
                continue
            
            link = original['link']
            title_normalized = original['title'].lower().strip()
            
            if link in seen_links or title_normalized in seen_titles:
                continue
            
            seen_links.add(link)
            seen_titles.add(title_normalized)
            
            first_decision = selection_info['decisions'][0]
            
            original['category'] = first_decision.get('category', 'Priority')
            original['reason'] = first_decision.get('reason', 'Structural significance')
            original['selected_by'] = selection_info['models']
            
            final_articles.append(original)
        
        final_articles = semantic_deduplication(final_articles, similarity_threshold=0.6)
        
        print(f"\nRESULTS:", flush=True)
        print(f"   Total articles available: {len(articles)}", flush=True)
        print(f"   Unique articles selected: {len(final_articles)}", flush=True)
        
        save_xml(final_articles)
        print("\nScript completed successfully!", flush=True)

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)[:100]}"
        print(f"::error::{error_msg}", flush=True)
        save_xml([], error_message=error_msg)
        sys.exit(0)

if __name__ == "__main__":
    main()

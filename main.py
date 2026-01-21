#!/usr/bin/env python3
# curator_ensemble_with_clustering.py
import os
import json
import requests
import time
import sys
import re
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Configuration
MAX_FEED_ITEMS = 100
URLS = [
    "https://evilgodfahim.github.io/bdit/daily_feed_2.xml",
    "https://evilgodfahim.github.io/bdit/daily_feed.xml",
    "https://evilgodfahim.github.io/edit/daily_feed.xml"
]

MODELS = [
    {"name": "kimi-k2-instruct-0905", "display": "Kimi-K2-Instruct", "batch_size": 50, "api": "fyra"},
    {"name": "meta-llama/llama-3.3-70b-instruct", "display": "Llama-3.3-70B", "batch_size": 50, "api": "openrouter"},
    {"name": "qwen/qwen3-32b", "display": "Qwen-3-32B", "batch_size": 25, "api": "groq"},
    {"name": "openai/gpt-oss-120b", "display": "GPT-OSS-120B", "batch_size": 25, "api": "groq"},
    {"name": "mistral-small-latest", "display": "Mistral-Small", "batch_size": 40, "api": "mistral"},
    {"name": "gemini-2.5-flash-lite", "display": "Gemini-2.5-Flash-Lite", "batch_size": 100, "api": "google"}
]

# API Keys and URLs
GROQ_API_KEY = os.environ.get("GEM")
OPENROUTER_API_KEY = os.environ.get("OP")
FYRA_API_KEY = os.environ.get("FRY")
MISTRAL_API_KEY = os.environ.get("GEM2")
GOOGLE_API_KEY = os.environ.get("LAM")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
FYRA_API_URL = "https://fyra.im/v1/chat/completions"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
GOOGLE_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

SYSTEM_PROMPT = """You are a Chief Information Filter.
Your task is to select headlines with structural and lasting significance.
Return only a JSON array of selected IDs (e.g. [0,5,12])."""

DEBUG = False

def is_bangla(text):
    return any(0x0980 <= ord(c) <= 0x09FF for c in (text or ""))

def save_xml(data, filename, error_message=None):
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    feed_title = "Elite News Feed"
    feed_title += " (English)" if "overflow" in filename else " (Bangla)"
    ET.SubElement(channel, "title").text = feed_title
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    ET.SubElement(channel, "link").text = "https://github.com/evilgodfahim"
    ET.SubElement(channel, "description").text = "AI-curated structural news feed"
    if error_message:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "System Error"
        ET.SubElement(item, "description").text = f"Script failed: {error_message}"
        ET.SubElement(item, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")
    elif not data:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "End of Feed"
        ET.SubElement(item, "description").text = "No additional articles in this feed."
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
        print(f"   Saved {len(data) if data else 0} items to {filename}", flush=True)
    except Exception as e:
        print(f"::error::Failed to write XML {filename}: {e}", flush=True)

def fetch_titles_only():
    all_articles = []
    seen_links = set()
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=26)
    print(f"Time Filter: Articles after {cutoff_time.strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
    headers = {'User-Agent': 'BCS-Curator/3.0-Ensemble'}
    for url in URLS:
        try:
            r = requests.get(url, headers=headers, timeout=10)
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
                if not link:
                    guid = item.find('guid')
                    link = guid.text if guid is not None else ""
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
        except Exception:
            continue
    print(f"Loaded {len(all_articles)} unique headlines", flush=True)
    return all_articles

# robust extractor reused
def extract_json_from_text(text):
    if not text:
        return None
    text = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start_idx = None
    for i, ch in enumerate(text):
        if ch in '[{':
            start_idx = i
            break
    if start_idx is None:
        return None
    i = start_idx
    stack = []
    in_str = None
    esc = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == in_str:
                in_str = None
        else:
            if ch == '"' or ch == "'":
                in_str = ch
            elif ch == '[':
                stack.append(']')
            elif ch == '{':
                stack.append('}')
            elif ch == ']' or ch == '}':
                if not stack:
                    break
                expected = stack.pop()
                if ch != expected:
                    break
                if not stack:
                    end_idx = i + 1
                    candidate = text[start_idx:end_idx]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
                        try:
                            return json.loads(cleaned)
                        except Exception:
                            return None
        i += 1
    s = text.find('[')
    e = text.rfind(']')
    if s != -1 and e != -1 and e > s:
        candidate = text[s:e+1]
        try:
            return json.loads(candidate)
        except Exception:
            try:
                cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
                return json.loads(cleaned)
            except Exception:
                return None
    return None

def call_model(model_info, batch):
    prompt_list = [f"{a['id']}: {a['title']}" for a in batch]
    prompt_text = "\n".join(prompt_list)
    api_type = model_info.get("api", "groq")
    if api_type == "openrouter":
        api_url = OPENROUTER_API_URL; api_key = OPENROUTER_API_KEY
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model_info["name"], "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt_text}], "temperature": 0.3}
    elif api_type == "fyra":
        api_url = FYRA_API_URL; api_key = FYRA_API_KEY
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model_info["name"], "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt_text}], "temperature": 0.3}
    elif api_type == "mistral":
        api_url = MISTRAL_API_URL; api_key = MISTRAL_API_KEY
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model_info["name"], "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt_text}], "temperature": 0.3}
    elif api_type == "google":
        api_url = f"{GOOGLE_API_URL}/{model_info['name']}:generateContent?key={GOOGLE_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt_text}"}]}], "generationConfig": {"temperature": 0.3}}
    else:
        api_url = GROQ_API_URL; api_key = GROQ_API_KEY
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model_info['name'], "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt_text}], "temperature": 0.3}
    max_retries = 5
    base_wait = 30
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=90)
            if response.status_code == 200:
                try:
                    response_data = response.json()
                except Exception:
                    continue
                content = None
                if isinstance(response_data, dict):
                    cand = response_data.get('candidates') or response_data.get('outputs') or []
                    if cand:
                        try:
                            content = cand[0]['content']['parts'][0]['text'].strip()
                        except Exception:
                            pass
                    if not content:
                        try:
                            content = response_data['choices'][0]['message']['content'].strip()
                        except Exception:
                            pass
                if not content:
                    content = response.text
                if content.startswith("```"):
                    content = content.replace("```json", "").replace("```", "").strip()
                parsed_data = extract_json_from_text(content)
                if parsed_data is not None and isinstance(parsed_data, list):
                    return parsed_data
                else:
                    time.sleep(2)
            elif response.status_code == 429:
                wait_time = base_wait * (2 ** attempt)
                time.sleep(wait_time)
                continue
            elif response.status_code >= 500:
                time.sleep(10)
                continue
        except requests.exceptions.RequestException:
            time.sleep(5)
        time.sleep(2)
    return []

def call_gemini_cluster(all_articles, model_name="gemini-2.5-flash-lite", min_similarity=0.5):
    if not GOOGLE_API_KEY:
        print("::warning::Google API key missing; skipping clustering.", flush=True)
        return None
    lines = []
    for a in all_articles:
        title = (a['title'] or "").replace("\n", " ").strip()
        desc = (a.get('description') or "").replace("\n", " ").strip()
        lines.append(f"{a['id']}\t{title}\t{a.get('link','')}\t{desc}")
    content_block = "\n".join(lines)
    system = ("You are a strict clustering assistant. Input is a tab-separated list: id<TAB>title<TAB>link<TAB>description. "
              f"Cluster headlines that are near-duplicates or strongly about the same event/impact. Only group items when similarity is approximately >= {int(min_similarity*100)}% (i.e. near-50% or greater). "
              "Choose one main representative per cluster (prefer the clearest title). Output VALID JSON only: an array of objects with fields {\"cluster_id\":int, \"main\":id, \"members\":[ids...]}. No commentary, no markdown, no code fences.")
    user = f"ARTICLES:\n{content_block}"
    api_url = f"{GOOGLE_API_URL}/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": system}, {"text": user}]}], "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2000}}
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = None
        if isinstance(data, dict):
            cand = data.get('candidates') or data.get('outputs') or []
            if cand:
                try:
                    text = cand[0]['content']['parts'][0]['text'].strip()
                except Exception:
                    pass
        if text is None:
            text = resp.text
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        parsed = extract_json_from_text(text)
        
        # Handle wrapped responses
        if isinstance(parsed, dict):
            # Try common wrapper keys
            for key in ['clusters', 'data', 'result', 'output']:
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
        
        if not isinstance(parsed, list):
            if DEBUG:
                print("Gemini cluster returned invalid format (expected JSON list).", flush=True)
                print("Response text:", text[:2000], flush=True)
                print("Parsed type:", type(parsed), flush=True)
                print("Parsed value:", parsed, flush=True)
            return None
        validated = []
        for i, c in enumerate(parsed):
            if not isinstance(c, dict): continue
            if 'members' not in c or 'main' not in c: continue
            try:
                members = [int(x) for x in c['members']]
                main = int(c['main'])
            except Exception:
                continue
            validated.append({"cluster_id": int(c.get("cluster_id", i)), "main": main, "members": members})
        return validated
    except Exception:
        return None

def main():
    print("=" * 60, flush=True)
    print("Elite News Curator - Multi-API Ensemble + Clustering", flush=True)
    print("=" * 60, flush=True)
    if not GROQ_API_KEY:
        print("::error::GEM environment variable is missing!", flush=True)
        sys.exit(1)
    needs_openrouter = any(m.get("api") == "openrouter" for m in MODELS)
    if needs_openrouter and not OPENROUTER_API_KEY:
        print("::error::OP environment variable is missing!", flush=True)
        sys.exit(1)
    needs_fyra = any(m.get("api") == "fyra" for m in MODELS)
    if needs_fyra and not FYRA_API_KEY:
        print("::error::FRY environment variable is missing!", flush=True)
        sys.exit(1)
    needs_mistral = any(m.get("api") == "mistral" for m in MODELS)
    if needs_mistral and not MISTRAL_API_KEY:
        print("::error::GEM2 environment variable is missing!", flush=True)
        sys.exit(1)
    needs_google = any(m.get("api") == "google" for m in MODELS)
    if needs_google and not GOOGLE_API_KEY:
        print("::error::LAM environment variable is missing!", flush=True)
        sys.exit(1)
    articles = fetch_titles_only()
    if not articles:
        save_xml([], "filtered_feed.xml")
        save_xml([], "filtered_feed_overflow.xml")
        return
    model_batches = {}
    for model_info in MODELS:
        bs = model_info['batch_size']
        model_batches[model_info['name']] = [articles[i:i + bs] for i in range(0, len(articles), bs)]
    max_batch_count = max(len(b) for b in model_batches.values())
    MAX_BATCHES_LIMIT = 20
    selections_map = {}
    for batch_idx in range(min(MAX_BATCHES_LIMIT, max_batch_count)):
        for model_info in MODELS:
            m_name = model_info['name']
            if batch_idx >= len(model_batches[m_name]): continue
            decisions = call_model(model_info, model_batches[m_name][batch_idx])
            if decisions:
                for aid in decisions:
                    if 0 <= aid < len(articles):
                        if aid not in selections_map:
                            selections_map[aid] = {'models': [], 'count': 0}
                        selections_map[aid]['models'].append(model_info['display'])
                        selections_map[aid]['count'] += 1
            time.sleep(8)
        if batch_idx < min(MAX_BATCHES_LIMIT, max_batch_count) - 1:
            time.sleep(20)
    final_articles = []
    for aid, info in selections_map.items():
        if info['count'] >= 2:
            art = articles[aid].copy()
            art['selected_by'] = info['models']
            art['category'] = 'BCS/Bank/GK'
            art['reason'] = 'Selected by multi-model consensus'
            final_articles.append(art)
    if not final_articles:
        save_xml([], "filtered_feed.xml")
        save_xml([], "filtered_feed_overflow.xml")
        return
    clusters = call_gemini_cluster(final_articles, model_name="gemini-2.5-flash-lite", min_similarity=0.5)
    if not clusters:
        bangla_articles = [a for a in final_articles if is_bangla(a['title'])]
        english_articles = [a for a in final_articles if not is_bangla(a['title'])]
        save_xml(bangla_articles, "filtered_feed.xml")
        save_xml(english_articles, "filtered_feed_overflow.xml")
        return
    cluster_map = {}
    used_ids = set()
    for c in clusters:
        cid = c['cluster_id']
        members = c['members']
        main = c['main'] if c['main'] in members else (members[0] if members else None)
        if main is None: continue
        cluster_map[cid] = {"main": main, "members": members}
        used_ids.update(members)
    next_cid = max(cluster_map.keys()) + 1 if cluster_map else 0
    for art in final_articles:
        if art['id'] not in used_ids:
            cluster_map[next_cid] = {"main": art['id'], "members": [art['id']]}
            next_cid += 1
    clustered_items = []
    for cid, info in cluster_map.items():
        main_id = info['main']
        members = info['members']
        main_art = next((a for a in final_articles if a['id'] == main_id), None)
        if not main_art: continue
        similar_html = ""
        sims = [m for m in members if m != main_id]
        if sims:
            similar_html += "<p><b>Similar items:</b></p><ul>"
            for sid in sims:
                art = next((a for a in final_articles if a['id'] == sid), None)
                if art:
                    safe_title = art['title']
                    safe_link = art.get('link', '#')
                    similar_html += f"<li><a href=\"{safe_link}\">{safe_title}</a></li>"
            similar_html += "</ul>"
        new_item = main_art.copy()
        new_item['description'] = (new_item.get('description','') or '') + "<hr/>" + similar_html
        new_item['cluster_id'] = cid
        clustered_items.append(new_item)
    bangla_articles = [a for a in clustered_items if is_bangla(a['title'])]
    english_articles = [a for a in clustered_items if not is_bangla(a['title'])]
    save_xml(bangla_articles, "filtered_feed.xml")
    save_xml(english_articles, "filtered_feed_overflow.xml")

if __name__ == "__main__":
    main()
import json
import os
import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote, quote

EXPORTS_DIR = "exports"
DB_PATH = "database.json"
CACHE_PATH = ".github/scripts/scrape_cache.json"

BLOCKLIST = {
    "furrybellygifs", "furrybellygifschat",
    "furrybellyhub",
    "furrybellyirl", "furrybellyirlchat",
    "furrybellynsfwc", "furrybellynsfwchat",
    "furrybellyvr", "furrybellyworship", "furrybellylove",
    "furryburps", "furryburpschat",
}

def log(msg):
    print(msg, flush=True)

def load_db():
    log(f"[DB] Loading {DB_PATH}...")
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            log(f"[DB] Loaded. Current creators: {len(data.get('creators', []))}")
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log(f"[DB] Failed to load ({e}). Starting fresh.")
        return {"last_updated": "", "creators": []}

def save_db(data):
    log(f"[DB] Saving {len(data.get('creators', []))} creators to {DB_PATH}")
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log("[DB] Save complete.")

def load_cache():
    if os.path.exists(CACHE_PATH):
        log(f"[CACHE] Loading from {CACHE_PATH}")
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    log("[CACHE] No cache file found.")
    return {}

def save_cache(cache):
    log(f"[CACHE] Saving {len(cache)} entries to {CACHE_PATH}")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
        f.write("\n")

def extract_text_from_message(msg):
    text = msg.get("text", "")
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return text if isinstance(text, str) else ""

def extract_urls_and_mentions(text):
    found = []
    raw_urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]()]+', text)
    for url in raw_urls:
        url = url.rstrip('.,;:!?>\'\"')
        found.append(("url", url))
    md_links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', text)
    for _, url in md_links:
        url = url.strip()
        if url.startswith("http"):
            url = url.rstrip('.,;:!?>\'\"')
            found.append(("url", url))
    mentions = re.findall(r'@([a-zA-Z0-9_.]+)', text)
    for m in mentions:
        found.append(("mention", m))
    return found

def clean_name(name):
    if not name:
        return None
    original = name
    name = name.strip()
    if name.startswith("@"):
        name = name[1:]
    name = name.split("?")[0].split("#")[0]
    for suffix in (".bsky.social", ".wobbl.xyz.ap.brid.gy"):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
    if name.startswith("did:plc:"):
        log(f"  [CLEAN] Rejected '{original}': Bluesky DID")
        return None
    stripped = name.lower().rstrip('.,;:!?)')
    if stripped in BLOCKLIST:
        log(f"  [CLEAN] Rejected '{original}': blocklisted")
        return None
    if name.startswith("__"):
        log(f"  [CLEAN] Rejected '{original}': label format")
        return None
    name = name.strip('/@#_')
    if len(name) < 2 or len(name) > 40:
        log(f"  [CLEAN] Rejected '{original}': length {len(name)}")
        return None
    return name

def extract_from_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = unquote(parsed.path)

    if domain.startswith("www."):
        domain = domain[4:]

    log(f"  [URL] Parsing: {domain}{path}")

    if domain in ("t.me", "telegram.me", "mega.nz"):
        log(f"  [URL] Skipping: Telegram/MEGA")
        return None

    if domain in ("bsky.app", "bskye.app", "bskyx.app", "cbsky.app",
                  "fxbsky.app", "vxbsky.app", "xbsky.app", "psky.app"):
        m = re.search(r'/profile/([^/?#]+)', path)
        if m:
            log(f"  [URL] Bluesky profile: {m.group(1)}")
            return clean_name(m.group(1))
        log(f"  [URL] Bluesky but no /profile/")
        return None

    if domain in ("twitter.com", "x.com", "nitter.net",
                  "fixupx.com", "fixvx.com", "fxtwitter.com", "girlcockx.com",
                  "mpregx.com", "pxtwitter.com", "stupidpenisx.com",
                  "twittpr.com", "vxtwitter.com", "xcancel.com"):
        parts = [p for p in path.split("/") if p]
        if parts and parts[0] not in ("i", "home", "search", "explore", "intent", "status", "hashtag"):
            log(f"  [URL] Twitter/X user: {parts[0]}")
            return clean_name(parts[0])
        log(f"  [URL] Twitter/X but no valid user")
        return None

    if domain in ("tiktok.com", "tiktokez.com", "tiktxk.com", "tnktok.com",
                  "vm.tfxktok.com", "vm.tiktokez.com", "vm.tiktok.com",
                  "www.tnktok.com", "vxtiktok.com", "tfxktok.com"):
        m = re.search(r'/@([^/?#]+)', path)
        if m:
            log(f"  [URL] TikTok user: {m.group(1)}")
            return clean_name(m.group(1))
        if domain.startswith("vm."):
            log(f"  [URL] TikTok VM shortlink")
            return scrape_with_cache(url, "tiktok_vm")
        parts = [p for p in path.split("/") if p]
        if parts and parts[0].startswith('@'):
            log(f"  [URL] TikTok user: {parts[0][1:]}")
            return clean_name(parts[0][1:])
        log(f"  [URL] TikTok but no user found")
        return None

    if domain in ("twitch.tv", "clips.twitch.tv", "www.twitch.tv"):
        parts = [p for p in path.split("/") if p]
        if not parts:
            return None
        if parts[0] == 'videos':
            log(f"  [URL] Twitch VOD skipped")
            return None
        if parts[0] == 'clip' and len(parts) >= 2:
            log(f"  [URL] Twitch clip skipped")
            return None
        if parts[0] not in ('directory', 'search', 'settings', 'login', 'videos', 'clip', 'clips'):
            log(f"  [URL] Twitch channel: {parts[0]}")
            return clean_name(parts[0])
        log(f"  [URL] Twitch system page skipped")
        return None

    if domain in ("deviantart.com", "www.deviantart.com"):
        parts = [p for p in path.split("/") if p]
        if not parts:
            return None
        if parts[0] in ('art', 'journal', 'browse', 'search', 'groups', 'shop', 'prints', 'tag', 'tags'):
            log(f"  [URL] DeviantArt post page skipped")
            return None
        log(f"  [URL] DeviantArt user: {parts[0]}")
        return clean_name(parts[0])

    if domain in ("youtube.com", "youtu.be", "koutube.com"):
        log(f"  [URL] YouTube - scraping")
        return scrape_with_cache(url, "youtube")

    if domain in ("instagram.com", "ddinstagram.com", "eeinstagram.com",
                  "kkinstagram.com"):
        parts = [p for p in path.split("/") if p]
        if not parts:
            return None
        if parts[0] in ('p', 'reel', 'tv', 'explore', 'accounts'):
            log(f"  [URL] Instagram post - scraping")
            return scrape_with_cache(url, "instagram")
        if parts[0] == 'stories' and len(parts) >= 2:
            log(f"  [URL] Instagram story user: {parts[1]}")
            return clean_name(parts[1])
        if len(parts) == 1:
            log(f"  [URL] Instagram profile: {parts[0]}")
            return clean_name(parts[0])
        log(f"  [URL] Instagram fallback scrape")
        return scrape_with_cache(url, "instagram")

    if domain in ("furaffinity.net", "d.furaffinity.net", "fxfuraffinity.net",
                  "fxrafinity.net", "xfuraffinity.net", "vxfuraffinity.net"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] == 'user':
            log(f"  [URL] FA user: {parts[1]}")
            return clean_name(parts[1])
        if '/view/' in path:
            log(f"  [URL] FA submission - scraping")
            return scrape_with_cache(url, "furaffinity")
        log(f"  [URL] FA but no user/view")
        return None

    if domain in ("facebook.com", "facebed.com"):
        log(f"  [URL] Facebook - scraping")
        return scrape_with_cache(url, "facebook")

    log(f"  [URL] Unrecognized domain, skipped")
    return None

def scrape_with_cache(url, platform):
    cache = load_cache()
    if url in cache:
        val = cache[url]
        log(f"  [SCRAPE] Cache hit: {val}")
        return clean_name(val) if val else None

    log(f"  [SCRAPE] Fetching {platform}: {url}")
    result = None
    try:
        if platform == "youtube":
            result = scrape_youtube(url)
        elif platform == "instagram":
            result = scrape_instagram(url)
        elif platform == "furaffinity":
            result = scrape_furaffinity(url)
        elif platform == "facebook":
            result = scrape_facebook(url)
        elif platform == "tiktok_vm":
            result = scrape_tiktok_vm(url)
    except Exception as e:
        log(f"  [SCRAPE] ERROR: {e}")

    log(f"  [SCRAPE] Result: {result}")
    cache[url] = result
    save_cache(cache)
    return clean_name(result) if result else None

def scrape_youtube(url):
    normalized = url.replace("koutube.com", "youtube.com")
    oembed = f"https://www.youtube.com/oembed?url={quote(normalized, safe='')}&format=json"
    r = requests.get(oembed, timeout=5)
    if r.status_code == 200:
        return r.json().get("author_name")
    return None

def scrape_instagram(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, timeout=5, headers=headers, allow_redirects=True)
    if r.status_code != 200:
        return None
    m = re.search(r'<title[^>]*>([^<]+)</title>', r.text, re.I)
    if m:
        title = m.group(1).strip()
        m2 = re.search(r'by\s+(@?[\w.]+)\s+on\s+Instagram', title, re.I)
        if m2:
            return m2.group(1).lstrip('@')
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.I)
    if m:
        content = m.group(1)
        m2 = re.search(r'(@?[\w.]+)', content)
        if m2:
            return m2.group(1).lstrip('@')
    return None

def scrape_furaffinity(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, timeout=5, headers=headers)
    if r.status_code != 200:
        return None
    m = re.search(r'/user/([^/"\'\s<>]+)', r.text)
    if m:
        return m.group(1)
    m = re.search(r'<title[^>]*>([^<]+)</title>', r.text, re.I)
    if m:
        m2 = re.search(r'by\s+([^<"\s]+)', m.group(1), re.I)
        if m2:
            return m2.group(1)
    return None

def scrape_facebook(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, timeout=5, headers=headers, allow_redirects=True)
    if r.status_code != 200:
        return None
    m = re.search(r'<title[^>]*>([^<]+)</title>', r.text, re.I)
    if m:
        title = m.group(1).strip()
        if '|' in title:
            return title.split('|')[0].strip()
    return None

def scrape_tiktok_vm(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.head(url, timeout=5, headers=headers, allow_redirects=True)
    final = r.url
    parsed = urlparse(final)
    path = unquote(parsed.path)
    m = re.search(r'/@([^/?#]+)', path)
    if m:
        return m.group(1)
    return None

def merge_creators(existing, new_names):
    log(f"[MERGE] Merging {len(existing)} existing + {len(new_names)} new")
    best = {}
    for name in existing + new_names:
        key = name.lower()
        if key not in best:
            best[key] = name
        else:
            if sum(1 for c in name if c.isupper()) > sum(1 for c in best[key] if c.isupper()):
                best[key] = name
    result = sorted(best.values(), key=str.lower)
    log(f"[MERGE] Result: {len(result)} unique creators")
    return result

def main():
    log("=" * 60)
    log("STARTING TELEGRAM EXPORT PROCESSOR")
    log("=" * 60)

    db = load_db()
    existing = db.get("creators", [])
    extracted = set()
    processed_files = []

    if not os.path.exists(EXPORTS_DIR):
        log(f"[ERROR] Exports directory '{EXPORTS_DIR}' not found!")
        return

    files = sorted([f for f in os.listdir(EXPORTS_DIR) if f.endswith('.json')])
    log(f"[FILES] Found {len(files)} JSON file(s): {files}")

    if not files:
        log("[WARN] No JSON files to process. Exiting.")
        return

    for filename in files:
        filepath = os.path.join(EXPORTS_DIR, filename)
        log(f"\n{'='*40}")
        log(f"[FILE] Processing: {filename}")
        log(f"{'='*40}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            log(f"[ERROR] Invalid JSON in {filename}: {e}")
            continue

        messages = data.get("messages", [])
        log(f"[FILE] Total messages: {len(messages)}")
        count = 0
        
        for msg in messages:
            if msg.get("type") != "message":
                continue
            
            text = extract_text_from_message(msg)
            if not text.strip():
                continue
            
            items = extract_urls_and_mentions(text)
            if items:
                log(f"\n  [MSG] Found {len(items)} item(s)")
            
            for kind, value in items:
                if kind == "mention":
                    log(f"  [MENTION] Raw: @{value}")
                    cleaned = clean_name(value)
                    if cleaned:
                        log(f"  [MENTION] -> ACCEPTED: {cleaned}")
                        extracted.add(cleaned)
                    else:
                        log(f"  [MENTION] -> REJECTED")
                elif kind == "url":
                    log(f"  [LINK] {value}")
                    cleaned = extract_from_url(value)
                    if cleaned:
                        log(f"  [LINK] -> ACCEPTED: {cleaned}")
                        extracted.add(cleaned)
                    else:
                        log(f"  [LINK] -> REJECTED")
            
            count += 1
        
        log(f"[FILE] Scanned {count} text messages")
        processed_files.append(filepath)

    log(f"\n{'='*60}")
    log(f"[SUMMARY] Extracted {len(extracted)} unique candidates:")
    for name in sorted(extracted):
        log(f"  - {name}")
    log(f"{'='*60}")

    merged = merge_creators(existing, list(extracted))
    log(f"[FINAL] Total creators in database: {len(merged)}")

    db["creators"] = merged
    save_db(db)

    log(f"\n[CLEANUP] Deleting {len(processed_files)} processed file(s)...")
    for filepath in processed_files:
        os.remove(filepath)
        log(f"  Deleted: {os.path.basename(filepath)}")

    log("\n" + "=" * 60)
    log("PROCESSING COMPLETE")
    log("=" * 60)

if __name__ == "__main__":
    main()

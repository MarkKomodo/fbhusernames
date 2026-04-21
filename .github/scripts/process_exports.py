import json
import os
import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote, quote

# ─── PATHS ───
EXPORTS_DIR = "exports"
DB_PATH = "database.json"
CACHE_PATH = ".github/scripts/scrape_cache.json"

# ─── CONFIG ───
BLOCKLIST = {
    "furrybellyhub", "furrybellygifs", "furrybellyirl", "furrybellynsfwc",
    "furrybellynsfwchat", "furrybellynsfwfchat", "furrybellyvr",
    "furrybellyworship", "furrybellyirlchat", "furryburps", "furryburpschat",
    "fursuitbellies",
}

# ─── HELPERS ───
def load_db():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_updated": "", "creators": []}

def save_db(data):
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
        f.write("\n")

# ─── TELEGRAM JSON PARSING ───
def extract_text_from_message(msg):
    """Flatten Telegram's text field (string or array of entities) into plain text."""
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

# ─── EXTRACTION ───
def extract_urls_and_mentions(text):
    found = []
    # Raw URLs
    for m in re.finditer(r'https?://[^\s<>"{}|\\^`\[\]]+', text):
        url = m.group(0).rstrip('.,;:!?)>\'\"')
        found.append(("url", url))
    # Markdown links [text](url)
    for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', text):
        url = m.group(2).strip()
        if url.startswith("http"):
            url = url.rstrip('.,;:!?)>\'\"')
            found.append(("url", url))
    # @mentions
    for m in re.finditer(r'@([a-zA-Z0-9_.]+)', text):
        found.append(("mention", m.group(1)))
    return found

# ─── URL PARSING ───
def extract_from_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = unquote(parsed.path)

    if domain.startswith("www."):
        domain = domain[4:]

    # Skip Telegram entirely
    if domain in ("t.me", "telegram.me"):
        return None

    # Bluesky + alts
    if domain in ("bsky.app", "bskye.app", "bskyx.app", "cbsky.app",
                  "fxbsky.app", "vxbsky.app", "xbsky.app"):
        m = re.search(r'/profile/([^/?#]+)', path)
        if m:
            return clean_name(m.group(1))

    # Twitter/X + alts
    if domain in ("twitter.com", "x.com", "nitter.net",
                  "fixupx.com", "fixvx.com", "fxtwitter.com", "girlcockx.com",
                  "mpregx.com", "pxtwitter.com", "stupidpenisx.com",
                  "twittpr.com", "vxtwitter.com", "xcancel.com"):
        parts = [p for p in path.split("/") if p]
        if parts and parts[0] not in ("i", "home", "search", "explore", "intent"):
            return clean_name(parts[0])

    # TikTok + alts
    if domain in ("tiktok.com", "tiktokez.com", "tiktxk.com", "tnktok.com",
                  "vm.tfxktok.com", "vm.tiktokez.com", "vm.tiktok.com",
                  "www.tnktok.com"):
        m = re.search(r'/@([^/?#]+)', path)
        if m:
            return clean_name(m.group(1))
        if domain.startswith("vm."):
            return scrape_with_cache(url, "tiktok_vm")

    # YouTube + alts
    if domain in ("youtube.com", "youtu.be", "koutube.com"):
        return scrape_with_cache(url, "youtube")

    # Instagram + alts
    if domain in ("instagram.com", "ddinstagram.com", "eeinstagram.com",
                  "kkinstagram.com"):
        return scrape_with_cache(url, "instagram")

    # FurAffinity + alts
    if domain in ("furaffinity.net", "d.furaffinity.net", "fxfuraffinity.net",
                  "fxrafinity.net", "xfuraffinity.net"):
        if "/view/" in path:
            return scrape_with_cache(url, "furaffinity")

    # Facebook + alts
    if domain in ("facebook.com", "facebed.com"):
        return scrape_with_cache(url, "facebook")

    return None

# ─── SCRAPING WITH CACHE ───
def scrape_with_cache(url, platform):
    cache = load_cache()
    if url in cache:
        val = cache[url]
        return clean_name(val) if val else None

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
        print(f"Scrape error ({platform}): {e}")

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

# ─── CLEANING ───
def clean_name(name):
    if not name:
        return None

    name = name.strip()

    if name.startswith("@"):
        name = name[1:]

    if "?" in name:
        name = name.split("?")[0]

    for suffix in (".bsky.social", ".wobbl.xyz.ap.brid.gy"):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]

    if name.startswith("did:plc:"):
        return None

    if re.search(r'^[a-z]+bot$|admin|mod|support|announcement', name, re.I):
        return None

    if name.lower() in BLOCKLIST:
        return None

    if name.startswith("__") and name.endswith("__"):
        return None

    if looks_like_random_hash(name):
        return None

    name = name.strip("/@#")
    if len(name) < 2 or len(name) > 40:
        return None

    return name

def looks_like_random_hash(name):
    if len(name) < 15:
        return False
    has_lower = bool(re.search(r'[a-z]', name))
    has_upper = bool(re.search(r'[A-Z]', name))
    has_digit = bool(re.search(r'\d', name))
    has_special = bool(re.search(r'[_\-]', name))
    score = sum([has_lower, has_upper, has_digit, has_special])
    if len(name) <= 20 and score >= 3:
        return True
    if len(name) > 20 and score >= 2:
        return True
    if len(name) >= 12 and not re.search(r'[aeiouAEIOU]', name):
        return True
    return False

# ─── MERGE ───
def merge_creators(existing, new_names):
    best = {}
    for name in existing + new_names:
        key = name.lower()
        current = best.get(key, "")
        if sum(1 for c in name if c.isupper()) > sum(1 for c in current if c.isupper()):
            best[key] = name
    return sorted(best.values(), key=str.lower)

# ─── MAIN ───
def main():
    db = load_db()
    existing = db.get("creators", [])
    extracted = set()
    processed_files = []

    if not os.path.exists(EXPORTS_DIR):
        print("No exports folder found.")
        return

    files = [f for f in os.listdir(EXPORTS_DIR) if f.endswith('.json')]
    if not files:
        print("No JSON files to process.")
        return

    for filename in files:
        filepath = os.path.join(EXPORTS_DIR, filename)
        print(f"Processing {filename}...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"  Skipping {filename}: invalid JSON")
            continue

        messages = data.get("messages", [])
        count = 0
        
        for msg in messages:
            if msg.get("type") != "message":
                continue
            
            text = extract_text_from_message(msg)
            if not text.strip():
                continue
            
            for kind, value in extract_urls_and_mentions(text):
                if kind == "mention":
                    cleaned = clean_name(value)
                    if cleaned:
                        extracted.add(cleaned)
                elif kind == "url":
                    cleaned = extract_from_url(value)
                    if cleaned:
                        extracted.add(cleaned)
            
            count += 1
        
        print(f"  Scanned {count} messages")
        processed_files.append(filepath)

    print(f"Extracted {len(extracted)} new candidates")

    merged = merge_creators(existing, list(extracted))
    print(f"Total after merge: {len(merged)}")

    db["creators"] = merged
    save_db(db)

    # Delete processed files to keep exports/ clean
    for filepath in processed_files:
        os.remove(filepath)
        print(f"Deleted {os.path.basename(filepath)}")

if __name__ == "__main__":
    main()

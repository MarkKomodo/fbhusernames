import json
import os
import re
from datetime import datetime, timezone
from collections import Counter

# ─── CONFIG ───
DB_PATH = "database.json"

# Domains/suffixes to strip
STRIP_SUFFIXES = [".bsky.social", ".wobbl.xyz.ap.brid.gy"]

# Regex patterns
URL_TRACKING_RE = re.compile(r'\?.*$')  # strip ?t=..., ?s=..., etc
MENTION_RE = re.compile(r'@([a-zA-Z0-9_.]+)')
URL_RE = re.compile(r'https?://[^\s<>\"{}|\\^`\[\]]+')
DID_RE = re.compile(r'did:plc:[a-z0-9]+')
INTERNAL_RE = re.compile(r'^[a-z]+bot$|admin|mod|support|announcement', re.I)

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

def clean_name(name):
    """Apply all normalization rules."""
    name = name.strip()
    
    # Remove @ prefix
    if name.startswith("@"):
        name = name[1:]
    
    # Strip URL tracking parameters
    if "?" in name:
        name = URL_TRACKING_RE.sub("", name)
    
    # Strip known domain suffixes
    for suffix in STRIP_SUFFIXES:
        if name.lower().endswith(suffix.lower()):
            name = name[:-len(suffix)]
    
    # Ignore DIDs
    if DID_RE.match(name):
        return None
    
    # Ignore internal/generic names
    if INTERNAL_RE.search(name):
        return None
    
    # Ignore URLs that aren't usernames
    if name.startswith("http"):
        # Extract last path segment as potential username
        parts = name.rstrip("/").split("/")
        if len(parts) > 3:
            name = parts[-1]
        else:
            return None
    
    # Final cleanup
    name = name.strip("/@#")
    if len(name) < 2:
        return None
        
    return name

def extract_creators(text):
    """Extract potential creator names from raw text."""
    found = set()
    
    # Extract @mentions
    for match in MENTION_RE.finditer(text):
        found.add(match.group(1))
    
    # Extract URLs and treat path segments as potential names
    for match in URL_RE.finditer(text):
        url = match.group(0)
        # Skip media URLs
        if any(x in url for x in ['t.me/c/', 'telegram.org', 'youtube.com/watch']):
            continue
        parts = url.rstrip("/").split("/")
        if len(parts) > 3:
            found.add(parts[-1])
    
    # Also split by whitespace and grab standalone words that look like handles
    words = re.findall(r'[a-zA-Z0-9_.]+', text)
    for w in words:
        if len(w) >= 3 and w not in found:
            found.add(w)
    
    return found

def merge_creators(existing, new_names):
    """
    Case-insensitive deduplication.
    Preserve the version with the MOST uppercase letters.
    """
    # Build map: lowercase -> best version
    best = {}
    
    for name in existing:
        key = name.lower()
        current = best.get(key, "")
        # Prefer more uppercase letters
        if sum(1 for c in name if c.isupper()) > sum(1 for c in current if c.isupper()):
            best[key] = name
            
    for name in new_names:
        key = name.lower()
        current = best.get(key, "")
        if sum(1 for c in name if c.isupper()) > sum(1 for c in current if c.isupper()):
            best[key] = name
    
    return sorted(best.values(), key=str.lower)

def main():
    # Read payload from environment (sent by bot)
    payload_raw = os.environ.get("RAW_PAYLOAD", "{}")
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        payload = {}
    
    # The bot sends: {"text": "raw message content", "source": "telegram"}
    raw_text = payload.get("text", "")
    if not raw_text:
        print("No text payload received. Exiting.")
        return
    
    print(f"Received payload with {len(raw_text)} chars")
    
    # Load existing database
    db = load_db()
    existing = db.get("creators", [])
    print(f"Existing creators: {len(existing)}")
    
    # Extract and clean new names
    raw_found = extract_creators(raw_text)
    cleaned = []
    for name in raw_found:
        c = clean_name(name)
        if c:
            cleaned.append(c)
    
    print(f"Extracted {len(cleaned)} new candidates")
    
    # Merge
    merged = merge_creators(existing + cleaned, [])
    print(f"Total after merge: {len(merged)}")
    
    # Save
    db["creators"] = merged
    save_db(db)
    print("Database updated successfully.")

if __name__ == "__main__":
    main()

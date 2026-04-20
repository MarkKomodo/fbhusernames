import json
import re

DB_PATH = "database.json"

BLOCKLIST = {
    "furrybellyhub", "furrybellygifs", "furrybellyirl", "furrybellynsfwc",
    "furrybellynsfwchat", "furrybellynsfwfchat", "furrybellyvr",
    "furrybellyworship", "furrybellyirlchat", "furryburps", "furryburpschat",
    "fursuitbellies",
}

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

def clean_existing(name):
    name = name.strip()
    if name.startswith('@'):
        name = name[1:]
    if '?' in name:
        name = name.split('?')[0]
    for suffix in ('.bsky.social', '.wobbl.xyz.ap.brid.gy'):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
    if name.startswith('did:plc:'):
        return None
    if re.search(r'^[a-z]+bot$|admin|mod|support|announcement', name, re.I):
        return None
    if name.lower() in BLOCKLIST:
        return None
    if name.startswith('__') and name.endswith('__'):
        return None
    if looks_like_random_hash(name):
        return None
    name = name.strip('/@#')
    if len(name) < 2 or len(name) > 40:
        return None
    return name

def main():
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    creators = db.get("creators", [])
    cleaned = []
    removed = []

    for name in creators:
        c = clean_existing(name)
        if c:
            cleaned.append(c)
        else:
            removed.append(name)

    # Deduplicate preserving most-uppercase version
    best = {}
    for name in cleaned:
        key = name.lower()
        current = best.get(key, "")
        if sum(1 for x in name if x.isupper()) > sum(1 for x in current if x.isupper()):
            best[key] = name

    db["creators"] = sorted(best.values(), key=str.lower)

    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Before: {len(creators)}")
    print(f"After:  {len(db['creators'])}")
    print(f"Removed: {len(removed)}")
    print("\nSample of removed garbage:")
    for r in removed[:30]:
        print(f"  - {r}")

if __name__ == "__main__":
    main()

import json
import os

EXPORTS_DIR = "exports"
OUTPUT_FILE = "extracted_links.txt"

def extract_text(msg):
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

def main():
    lines = []
    if not os.path.exists(EXPORTS_DIR):
        print(f"Directory '{EXPORTS_DIR}' not found. Place script next to the exports folder.")
        return

    for filename in sorted(os.listdir(EXPORTS_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(EXPORTS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for msg in data.get("messages", []):
            if msg.get("type") != "message":
                continue
            text = extract_text(msg).strip()
            # Only keep messages containing links or user handles
            if text and ("http" in text or "@" in text):
                lines.append(text.replace("\n", " "))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"Extracted {len(lines)} messages to '{OUTPUT_FILE}' ({size_kb:.1f} KB)")

if __name__ == "__main__":
    main()

# 🐾 Furry Belly Hub — Content Creator Index

A live, searchable index of content creators extracted from Telegram channel exports. Hosted on **Carrd** via an iframe widget, with automated processing through **GitHub Actions**.

---

## 🌐 Live Widget

The widget is embedded on Carrd and displays the full creator database with live search:

- **Frontend:** Responsive HTML/CSS widget (iframe)
- **Data source:** `database.json` hosted on GitHub Pages
- **Cache-busting:** `?t=timestamp` ensures fresh data on every load

---

## 📁 Repository Structure
```
fbhusernames/
├── database.json                  # The live creator index
├── widget.html                    # Standalone widget (hosted via GitHub Pages)
├── exports/                       # Drop Telegram JSON exports here
│   └── .gitkeep
├── .github/
│   ├── workflows/
│   │   └── process-exports.yml    # GitHub Action: processes exports automatically
│   └── scripts/
│       ├── process_exports.py     # Python: extracts & cleans creator names
│       └── scrape_cache.json      # Cache for scraped URLs (YouTube, Instagram, etc.)
```

---

## 🔄 How It Works

### 1. Export from Telegram Desktop
1. Open **Telegram Desktop**
2. Go to your channel → **⋮** → **Export chat history**
3. Set format to **JSON**, uncheck all media (text only)
4. Save the `result.json` file

### 2. Upload to GitHub
1. Rename the export (e.g., `channel1.json`)
2. Upload it to the `exports/` folder in this repo
3. The file stays there until you trigger processing

### 3. Process the Export
1. Go to **Actions** → **Process Telegram Exports**
2. Click **Run workflow** → **Run workflow**
3. The Action will:
   - Reset `database.json` to empty
   - Extract all URLs and `@mentions` from the export
   - Scrape platforms (YouTube, Instagram, FurAffinity, Facebook, TikTok) for real usernames
   - Clean and deduplicate the list
   - Save the result to `database.json`
   - Delete the processed export files

### 4. View on Carrd
Refresh your Carrd page. The widget fetches the latest `database.json` automatically.

---

## 🔗 Supported Platforms

| Platform | Extraction Method | Example |
|----------|-------------------|---------|
| **Twitter / X** | URL path | `twitter.com/Username` → `Username` |
| **Bluesky** | URL path | `bsky.app/profile/Username` → `Username` |
| **TikTok** | URL path | `tiktok.com/@Username` → `Username` |
| **YouTube** | Scrape (oEmbed API) | `youtu.be/VIDEOID` → channel name |
| **Instagram** | Scrape (HTML) or path | `instagram.com/p/SHORTCODE` → author name |
| **FurAffinity** | URL path or scrape | `furaffinity.net/user/Username` → `Username` |
| **Facebook** | Scrape (HTML) | `facebook.com/...` → page name |
| **@mentions** | Plain text | `@Username` → `Username` |

**Skipped:** Telegram links (`t.me/...`), plain text words, tracking tokens, post IDs.

---

## 🛡️ Cleaning Rules

The processor automatically filters out:

- ❌ URL tracking parameters (`?t=...`, `?s=...`)
- ❌ Bluesky suffixes (`.bsky.social`, `.wobbl.xyz.ap.brid.gy`)
- ❌ Bluesky DIDs (`did:plc:...`)
- ❌ Your own community names (blocklisted)
- ❌ Names shorter than 2 or longer than 40 characters
- ❌ Duplicate names (case-insensitive, keeps most capitalized version)

---

## 🎨 Customization

### Badge Color
Edit the `--accent` CSS variable in `widget.html`:
```css
--accent: #FFD93D;  /* Current: yellow */
```

4. Click **Commit changes**

This README documents everything: the workflow, the supported platforms, the cleaning rules, and how to use it. Let me know if you want to add or change anything.

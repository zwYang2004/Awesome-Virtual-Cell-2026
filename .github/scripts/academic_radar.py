#!/usr/bin/env python3
"""
Academic Radar: Automated arXiv & Frontier Paper Scanner
Collects recent preprint candidates in Virtual Cells, Single-Cell Perturbation,
Flow Matching & Foundation Models into LATEST_RADAR.md without polluting the main README.
"""

import os
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RADAR_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "LATEST_RADAR.md")

SEARCH_QUERIES = [
    '(ti:"virtual cell" OR abs:"virtual cell")',
    '(ti:"single-cell perturbation" OR abs:"single-cell perturbation")',
    '(abs:"flow matching" AND (abs:"single-cell" OR abs:"scRNA"))',
    '(abs:"foundation model" AND (abs:"scRNA-seq" OR abs:"single cell"))',
]

def fetch_arxiv_papers(max_results=20):
    query = " OR ".join(SEARCH_QUERIES)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results)
    }
    url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    
    headers = {"User-Agent": "AcademicRadarBot/1.0 (https://github.com/zwYang2004/Awesome-Virtual-Cell-2026)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"[Error] Failed to query arXiv API: {e}")
        return []

    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns)
        summary = entry.find("atom:summary", ns)
        published = entry.find("atom:published", ns)
        link = entry.find("atom:id", ns)
        
        # authors
        authors = [a.find("atom:name", ns).text.strip() for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
        author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        
        # categories
        categories = [c.attrib.get("term") for c in entry.findall("atom:category", ns) if c.attrib.get("term")]
        
        if title is not None and link is not None:
            clean_title = re.sub(r"\s+", " ", title.text).strip()
            clean_summary = re.sub(r"\s+", " ", summary.text).strip() if summary is not None else ""
            pub_date = published.text[:10] if published is not None else datetime.now().strftime("%Y-%m-%d")
            
            papers.append({
                "id": link.text.strip(),
                "title": clean_title,
                "authors": author_str,
                "date": pub_date,
                "categories": categories[:3],
                "summary": clean_summary[:300] + ("..." if len(clean_summary) > 300 else ""),
                "url": link.text.strip()
            })
            
    return papers

def load_existing_ids():
    if not os.path.exists(RADAR_FILE):
        return set()
    with open(RADAR_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # Find all arxiv IDs like https://arxiv.org/abs/...
    return set(re.findall(r"https?://arxiv\.org/abs/[\w\.\/]+", content))

def update_radar_file(new_papers):
    existing_ids = load_existing_ids()
    unseen = [p for p in new_papers if p["url"] not in existing_ids]
    
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    if not os.path.exists(RADAR_FILE):
        header = f"""# 📡 Frontier Academic Radar (Weekly Candidate Pool)

> **Auto-curated by GitHub Actions | Managed by [zwYang2004](https://github.com/zwYang2004)**  
> This file acts as an automated triage buffer for newly published preprints from **arXiv & bioRxiv** regarding Virtual Cells, Single-Cell Perturbation, Flow Matching, and Cell Foundation Models.  
> 💡 *Only preprints evaluated as top-tier, methodologically sound, or benchmark-grounded will be promoted to the main [README.md](README.md).*

---

"""
    else:
        with open(RADAR_FILE, "r", encoding="utf-8") as f:
            header = f.read()
            
    if not unseen:
        print("[Info] No new unindexed papers discovered this run.")
        return False
        
    print(f"[Info] Found {len(unseen)} new candidate papers. Appending to LATEST_RADAR.md...")
    
    batch_markdown = f"\n### 🗓️ Radar Batch: {now_str}\n\n"
    for p in unseen:
        cats = " ".join([f"`{c}`" for c in p["categories"]])
        batch_markdown += f"- **[{p['title']}]({p['url']})**  \n"
        batch_markdown += f"  - **Authors**: {p['authors']} | **Date**: `{p['date']}` | **Tags**: {cats}  \n"
        batch_markdown += f"  - **Abstract**: *{p['summary']}*  \n"
        batch_markdown += f"  - [ ] **Review Status**: `Pending Review` *(Check box if promoted to main README)*  \n\n"
        
    # Prepend new batch right after the header block
    if "# 📡 Frontier Academic Radar" in header:
        parts = header.split("---\n\n", 1)
        if len(parts) == 2:
            updated_content = parts[0] + "---\n\n" + batch_markdown + parts[1]
        else:
            updated_content = header + "\n" + batch_markdown
    else:
        updated_content = header + "\n" + batch_markdown
        
    with open(RADAR_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)
        
    return True

if __name__ == "__main__":
    print("[Radar] Querying arXiv API for newest Virtual Cell candidates...")
    papers = fetch_arxiv_papers(max_results=15)
    print(f"[Radar] Fetched {len(papers)} papers from arXiv.")
    has_changes = update_radar_file(papers)
    if has_changes:
        print("[Radar] Successfully updated LATEST_RADAR.md.")
    else:
        print("[Radar] LATEST_RADAR.md is already up to date.")

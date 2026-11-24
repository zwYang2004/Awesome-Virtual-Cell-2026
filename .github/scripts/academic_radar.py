#!/usr/bin/env python3
"""
Academic Radar: Automated arXiv & Frontier Paper Scanner with Archiving
- Manages active buffer in LATEST_RADAR.md (current active batches)
- Automatically archives historical batches into radar/archive/YYYY/YYYY-MM.md
- Ranks candidate preprints by Elite Scholars and Methodological breakthroughs
"""

import os
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RADAR_FILE = os.path.join(BASE_DIR, "LATEST_RADAR.md")
ARCHIVE_DIR = os.path.join(BASE_DIR, "radar", "archive")

# Elite Scholars & Frontier Labs Whitelist (Public academic pioneers)
ELITE_AUTHORS = [
    "Fabian Theis", "F. Theis", "Aviv Regev", "A. Regev", "Bo Wang",
    "Jun Xia", "J. Xia", "Stan Z. Li", "S. Z. Li", "James Zou", "J. Zou",
    "Jianzhu Ma", "J. Ma", "Dana Pe'er", "Cole Trapnell", "Jure Leskovec",
    "Yaron Lipman", "Ricky T. Q. Chen", "Michael Bronstein", "Patrick Hsu",
    "David Baker", "Alexander Tong", "Smita Krishnaswamy", "Mohammad Lotfollahi",
    "Charlotte Bunne", "Emma Lundberg", "Stephen Quake"
]

HIGH_IMPACT_KEYWORDS = [
    "flow matching", "schrodinger bridge", "schrödinger bridge",
    "destructive sampling", "cellular trajectory", "perturbation prediction",
    "single-cell foundation model", "cell world model", "out-of-distribution perturbation",
    "combinatorial perturbation", "in silico simulation", "spatial perturbation"
]

SEARCH_QUERIES = [
    '(ti:"virtual cell" OR abs:"virtual cell")',
    '(ti:"single-cell perturbation" OR abs:"single-cell perturbation")',
    '(abs:"flow matching" AND (abs:"single-cell" OR abs:"scRNA"))',
    '(abs:"foundation model" AND (abs:"scRNA-seq" OR abs:"single cell"))',
    '(abs:"schrodinger bridge" AND abs:"single cell")',
]

def score_paper(paper):
    score = 0
    reasons = []
    
    for ea in ELITE_AUTHORS:
        if ea.lower() in paper["authors"].lower():
            score += 4
            reasons.append(f"Leading Lab: {ea}")
            break
            
    text = (paper["title"] + " " + paper["summary"]).lower()
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in text:
            score += 1.5
            reasons.append(kw)
            
    is_tier1 = score >= 3.0
    return score, is_tier1, reasons[:4]

def fetch_arxiv_papers(max_results=20):
    query = " OR ".join(SEARCH_QUERIES)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results)
    }
    url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AcademicRadarBot/2.1"})
    
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
        
        authors = [a.find("atom:name", ns).text.strip() for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
        author_str = ", ".join(authors[:4]) + (" et al." if len(authors) > 4 else "")
        categories = [c.attrib.get("term") for c in entry.findall("atom:category", ns) if c.attrib.get("term")]
        
        if title is not None and link is not None:
            clean_title = re.sub(r"\s+", " ", title.text).strip()
            clean_summary = re.sub(r"\s+", " ", summary.text).strip() if summary is not None else ""
            pub_date = published.text[:10] if published is not None else datetime.now().strftime("%Y-%m-%d")
            
            p = {
                "id": link.text.strip(),
                "title": clean_title,
                "authors": author_str,
                "date": pub_date,
                "categories": categories[:3],
                "summary": clean_summary[:350] + ("..." if len(clean_summary) > 350 else ""),
                "url": link.text.strip()
            }
            score, is_tier1, reasons = score_paper(p)
            p["score"] = score
            p["is_tier1"] = is_tier1
            p["reasons"] = reasons
            papers.append(p)
            
    return papers

def load_existing_ids():
    ids = set()
    if os.path.exists(RADAR_FILE):
        with open(RADAR_FILE, "r", encoding="utf-8") as f:
            ids.update(re.findall(r"https?://arxiv\.org/abs/[\w\.\/]+", f.read()))
    if os.path.exists(ARCHIVE_DIR):
        for root, _, files in os.walk(ARCHIVE_DIR):
            for file in files:
                if file.endswith(".md"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        ids.update(re.findall(r"https?://arxiv\.org/abs/[\w\.\/]+", f.read()))
    return ids

def archive_old_batches_if_needed():
    if not os.path.exists(RADAR_FILE):
        return
    with open(RADAR_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split by batch
    batches = re.split(r"(?=### 🗓️ Radar Batch: )", content)
    if len(batches) <= 4:
        return # keep up to 3-4 latest batches in main buffer
        
    header = batches[0]
    active_batches = batches[1:4]
    older_batches = batches[4:]
    
    now = datetime.now(timezone.utc)
    year = str(now.year)
    month_str = now.strftime("%Y-%m")
    
    target_dir = os.path.join(ARCHIVE_DIR, year)
    os.makedirs(target_dir, exist_ok=True)
    archive_file = os.path.join(target_dir, f"{month_str}.md")
    
    archive_content = f"# Radar Archive: {month_str}\n\n" + "".join(older_batches)
    with open(archive_file, "a", encoding="utf-8") as f:
        f.write(archive_content)
        
    updated_main = header + "".join(active_batches)
    with open(RADAR_FILE, "w", encoding="utf-8") as f:
        f.write(updated_main)
    print(f"[Archive] Moved {len(older_batches)} older batches to {archive_file}")

def update_radar_file(new_papers):
    existing_ids = load_existing_ids()
    unseen = [p for p in new_papers if p["url"] not in existing_ids]
    
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")
    
    if not os.path.exists(RADAR_FILE):
        header = f"""# 📡 Frontier Academic Radar (Active Triage Buffer)

> **Curated by GitHub Actions | Lead: [Zhiwen Yang](https://zwyang2004.github.io/)**  
> Automated screening for preprints in Virtual Cells, Perturbation Modeling, and Flow Matching.  
> 🌟 **Tier-1**: Flagged for leading groups (Theis, Regev, Bo Wang, Jun Xia, Stanford, etc.) and core mathematical leaps.  
> 💡 Historical batches are archived monthly under [`radar/archive/`](radar/archive/).

---

"""
    else:
        with open(RADAR_FILE, "r", encoding="utf-8") as f:
            header = f.read()
            
    if not unseen:
        print("[Info] No new preprints discovered.")
        return False
        
    tier1_papers = [p for p in unseen if p["is_tier1"]]
    tier2_papers = [p for p in unseen if not p["is_tier1"]]
    
    batch_markdown = f"\n### 🗓️ Radar Batch: {now_str}\n\n"
    if tier1_papers:
        batch_markdown += "#### 🌟 Tier-1 High-Priority Preprints (Leading Lab / Methodological Leap)\n\n"
        for p in tier1_papers:
            cats = " ".join([f"`{c}`" for c in p["categories"]])
            reasons_str = ", ".join([f"`{r}`" for r in p["reasons"]])
            batch_markdown += f"- **[{p['title']}]({p['url']})** &nbsp; *Score: {p['score']:.1f}*  \n"
            batch_markdown += f"  - **Authors**: {p['authors']} | **Date**: `{p['date']}` | **Tags**: {cats}  \n"
            batch_markdown += f"  - **Highlight**: {reasons_str}  \n"
            batch_markdown += f"  - **Abstract**: *{p['summary']}*  \n"
            batch_markdown += f"  - [ ] **Triage**: `Promote to Main Registry`  \n\n"
            
    if tier2_papers:
        batch_markdown += "#### 📌 Tier-2 Monitoring Preprints (General Candidate Stream)\n\n"
        for p in tier2_papers:
            cats = " ".join([f"`{c}`" for c in p["categories"]])
            batch_markdown += f"- **[{p['title']}]({p['url']})**  \n"
            batch_markdown += f"  - **Authors**: {p['authors']} | **Date**: `{p['date']}` | **Tags**: {cats}  \n"
            batch_markdown += f"  - **Abstract**: *{p['summary']}*  \n"
            batch_markdown += f"  - [ ] **Status**: `Pending Review`  \n\n"
        
    if "# 📡 Frontier Academic Radar" in header:
        parts = header.split("---\n\n", 1)
        updated_content = parts[0] + "---\n\n" + batch_markdown + (parts[1] if len(parts) > 1 else "")
    else:
        updated_content = header + "\n" + batch_markdown
        
    with open(RADAR_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)
        
    archive_old_batches_if_needed()
    return True

if __name__ == "__main__":
    papers = fetch_arxiv_papers(max_results=20)
    update_radar_file(papers)

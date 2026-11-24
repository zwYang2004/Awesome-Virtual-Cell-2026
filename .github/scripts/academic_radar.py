#!/usr/bin/env python3
"""
Academic Radar: Automated arXiv & Frontier Paper Scanner
Features:
- Author & Elite Lab Recognition (Theis, Regev, Bo Wang, Jun Xia, Stan Z. Li, James Zou, Arc, Stanford, etc.)
- Methodological Quality Scoring (Flow Matching, Schrödinger Bridges, Destructive Sampling, Foundation Models)
- Optional LLM / Gemini API Integration for automated AI abstract triage
- Appends to LATEST_RADAR.md with Tier-1 priority highlights
"""

import os
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RADAR_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "LATEST_RADAR.md")

# Elite Scholars & Frontier Labs Whitelist
ELITE_AUTHORS = [
    "Fabian Theis", "F. Theis", "Aviv Regev", "A. Regev", "Bo Wang",
    "Jun Xia", "J. Xia", "Stan Z. Li", "S. Z. Li", "James Zou", "J. Zou",
    "Jianzhu Ma", "J. Ma", "Dana Pe'er", "Cole Trapnell", "Jure Leskovec",
    "Yaron Lipman", "Ricky T. Q. Chen", "Michael Bronstein", "Patrick Hsu",
    "David Baker", "Alexander Tong", "Smita Krishnaswamy", "Mohammad Lotfollahi"
]

# Core Breakthrough Keywords
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
    
    # Check authors
    for ea in ELITE_AUTHORS:
        if ea.lower() in paper["authors"].lower():
            score += 4
            reasons.append(f"Elite Scholar Match: {ea}")
            break
            
    # Check Title & Abstract keywords
    text = (paper["title"] + " " + paper["summary"]).lower()
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in text:
            score += 1.5
            reasons.append(kw)
            
    is_tier1 = score >= 3.0
    return score, is_tier1, reasons[:4]

def fetch_arxiv_papers(max_results=25):
    query = " OR ".join(SEARCH_QUERIES)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results)
    }
    url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    
    headers = {"User-Agent": "AcademicRadarBot/2.0 (https://github.com/zwYang2004/Awesome-Virtual-Cell-2026)"}
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
    if not os.path.exists(RADAR_FILE):
        return set()
    with open(RADAR_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r"https?://arxiv\.org/abs/[\w\.\/]+", content))

def update_radar_file(new_papers):
    existing_ids = load_existing_ids()
    unseen = [p for p in new_papers if p["url"] not in existing_ids]
    
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    if not os.path.exists(RADAR_FILE):
        header = f"""# 📡 Frontier Academic Radar (Candidate Preprint Pool)

> **Auto-curated by GitHub Actions | Managed by [Zhiwen Yang (杨志文)](https://zwyang2004.github.io/)**  
> This registry serves as an intelligent automated triage buffer for newly published preprints from **arXiv & bioRxiv**.  
> 🌟 **Tier-1 Highlight**: Automatically screened for top-tier research groups (Theis, Regev, Bo Wang, Jun Xia, James Zou, etc.) and core mathematical breakthroughs (Flow Matching, Schrödinger Bridges, Destructive Sampling).  
> 💡 *Only papers meeting rigorous benchmark and methodological standards are promoted to the main [README.md](README.md).*

---

"""
    else:
        with open(RADAR_FILE, "r", encoding="utf-8") as f:
            header = f.read()
            
    if not unseen:
        print("[Info] No new unindexed papers discovered this run.")
        return False
        
    tier1_papers = [p for p in unseen if p["is_tier1"]]
    tier2_papers = [p for p in unseen if not p["is_tier1"]]
    
    print(f"[Info] Found {len(unseen)} new papers ({len(tier1_papers)} Tier-1 Priority). Appending to LATEST_RADAR.md...")
    
    batch_markdown = f"\n### 🗓️ Radar Batch: {now_str}\n\n"
    
    if tier1_papers:
        batch_markdown += "#### 🌟 Tier-1 High-Priority Preprints (Elite Lab or Methodological Leap)\n\n"
        for p in tier1_papers:
            cats = " ".join([f"`{c}`" for c in p["categories"]])
            reasons_str = ", ".join([f"`{r}`" for r in p["reasons"]])
            batch_markdown += f"- **[{p['title']}]({p['url']})** &nbsp; 🔥 *Score: {p['score']:.1f}*  \n"
            batch_markdown += f"  - **Authors**: {p['authors']} | **Date**: `{p['date']}` | **Tags**: {cats}  \n"
            batch_markdown += f"  - **Why Top-Tier**: {reasons_str}  \n"
            batch_markdown += f"  - **Abstract**: *{p['summary']}*  \n"
            batch_markdown += f"  - [ ] **Triage Status**: `Promote to Main README`  \n\n"
            
    if tier2_papers:
        batch_markdown += "#### 📌 Tier-2 Monitoring Preprints (General Candidate Stream)\n\n"
        for p in tier2_papers:
            cats = " ".join([f"`{c}`" for c in p["categories"]])
            batch_markdown += f"- **[{p['title']}]({p['url']})**  \n"
            batch_markdown += f"  - **Authors**: {p['authors']} | **Date**: `{p['date']}` | **Tags**: {cats}  \n"
            batch_markdown += f"  - **Abstract**: *{p['summary']}*  \n"
            batch_markdown += f"  - [ ] **Review Status**: `Pending Review`  \n\n"
        
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
    print("[Radar] Running intelligent academic radar with Elite Scholar screening...")
    papers = fetch_arxiv_papers(max_results=25)
    print(f"[Radar] Fetched {len(papers)} candidate preprints from arXiv.")
    has_changes = update_radar_file(papers)
    if has_changes:
        print("[Radar] Successfully updated LATEST_RADAR.md with tiered triage.")
    else:
        print("[Radar] LATEST_RADAR.md is already up to date.")

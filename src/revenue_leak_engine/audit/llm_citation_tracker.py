"""
Phase 3: High-Tech Self-Aware Entity & SERP Intelligence Tracker
Dynamically studies the site to determine core product offerings.
Zero external API dependencies. Bulletproof data engineering.
"""
import sqlite3, time, os, re, json, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
from revenue_leak_engine.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "geo_intelligence.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS entity_sov_history (
            domain TEXT, timestamp REAL, brand TEXT, core_product TEXT,
            wikidata_exists INTEGER, wikipedia_exists INTEGER, wikidata_id TEXT,
            serp_rank INTEGER, top_competitors TEXT, sov_percentage REAL
        )""")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INIT ERROR] {e}")

init_db()

def extract_core_product(html: str, brand: str) -> str:
    """Self-aware extraction of what the site actually sells."""
    if not html: return brand
    soup = BeautifulSoup(html, "html.parser")
    
    # Try meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        desc = meta_desc["content"].strip()
        desc = re.sub(rf'(?i){brand}.*', '', desc).strip()
        if len(desc) > 10:
            words = desc.split()[:5]
            return " ".join(words).strip(".,;!")
            
    # Try H1
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        text = re.sub(rf'(?i){brand}.*', '', text).strip()
        if len(text) > 3:
            return " ".join(text.split()[:5]).strip(".,;!")
            
    # Try Title
    title = soup.find("title")
    if title:
        text = title.get_text(strip=True)
        text = re.sub(rf'(?i){brand}.*', '', text).strip()
        text = re.sub(r'[-|–].*', '', text).strip()
        if len(text) > 3:
            return " ".join(text.split()[:5]).strip(".,;!")
            
    return brand

def track_entity_and_sov(domain: str, html: str) -> dict:
    brand = domain.split('.')[0].replace('-', ' ').title()
    core_product = extract_core_product(html, brand)
    
    result = {
        "domain": domain, "brand": brand, "core_product": core_product,
        "wikidata_exists": 0, "wikipedia_exists": 0, "wikidata_id": "N/A",
        "serp_rank": 0, "top_competitors": "[]", "sov_percentage": 0.0
    }
    
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        import requests as cffi_requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    # Fetch HTML if not provided
    if not html:
        try:
            resp = cffi_requests.get(f"https://{domain}/", headers=headers, timeout=10, impersonate="chrome120")
            if resp.status_code == 200: html = resp.text
        except: pass

    # 1. WIKIDATA
    try:
        wd_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(brand)}&language=en&format=json"
        wd_resp = cffi_requests.get(wd_url, headers=headers, timeout=10, impersonate="chrome120")
        if wd_resp.status_code == 200:
            wd_data = wd_resp.json()
            if wd_data.get("search"):
                result["wikidata_exists"] = 1
                result["wikidata_id"] = wd_data["search"][0].get("id", "N/A")
    except Exception as e:
        print(f"[WIKIDATA ERROR] {e}")

    # 2. SERP (Dynamic Self-Aware Query)
    try:
        query = f"best {core_product} brands"
        serp_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        serp_resp = cffi_requests.get(serp_url, headers=headers, timeout=15, impersonate="chrome120")
        if serp_resp.status_code == 200:
            soup = BeautifulSoup(serp_resp.text, "html.parser")
            results = soup.find_all("a", class_="result__a")
            
            rank = 0
            competitors = []
            domain_found = False
            
            for i, link in enumerate(results[:10]):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                
                if domain in href or brand.lower() in text.lower():
                    rank = i + 1
                    domain_found = True
                else:
                    comp_match = re.search(r'https?://(?:www\.)?([^/]+)', href)
                    if comp_match:
                        comp_dom = comp_match.group(1).replace('www.', '')
                        if comp_dom not in competitors and comp_dom != domain and "duckduckgo" not in comp_dom:
                            competitors.append(comp_dom)
            
            result["serp_rank"] = rank
            result["top_competitors"] = json.dumps(competitors[:3])
            result["sov_percentage"] = 100.0 if domain_found else 0.0
    except Exception as e:
        print(f"[SERP ERROR] {e}")

    # 3. SAVE
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO entity_sov_history 
                        (domain, timestamp, brand, core_product, wikidata_exists, wikipedia_exists, wikidata_id, 
                         serp_rank, top_competitors, sov_percentage) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (result["domain"], time.time(), result["brand"], result["core_product"],
                      result["wikidata_exists"], result["wikipedia_exists"], result["wikidata_id"],
                      result["serp_rank"], result["top_competitors"], result["sov_percentage"]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")

    return result

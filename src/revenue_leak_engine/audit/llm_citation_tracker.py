"""
Phase 3 & 6: Unified Entity, SERP, and LLM Citation Engine.
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
        cols = [row[1] for row in conn.execute("PRAGMA table_info(entity_sov_history)").fetchall()]
        if "top_competitor" not in cols:
            conn.execute("ALTER TABLE entity_sov_history ADD COLUMN top_competitor TEXT")
        if "competitor_schema_count" not in cols:
            conn.execute("ALTER TABLE entity_sov_history ADD COLUMN competitor_schema_count INTEGER")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS llm_citations (
            domain TEXT, timestamp REAL, model TEXT, prompt TEXT,
            brand_mentioned INTEGER, citation_count INTEGER, citation_urls TEXT, raw_response TEXT
        )""")
        cols = [row[1] for row in conn.execute("PRAGMA table_info(llm_citations)").fetchall()]
        if "citation_urls" not in cols:
            conn.execute("ALTER TABLE llm_citations ADD COLUMN citation_urls TEXT")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INIT ERROR] {e}")

init_db()

def extract_core_product(html: str, brand: str) -> str:
    if not html: return "premium products"
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    desc = soup.find("meta", attrs={"name": "description"})
    h1 = soup.find("h1")

    text_pool = " ".join([
        title.get_text(strip=True) if title else "",
        desc.get("content", "") if desc else "",
        h1.get_text(strip=True) if h1 else ""
    ]).lower()

    text_pool = re.sub(rf'\b{brand.lower()}\b', '', text_pool)

    keywords = ["skincare", "apparel", "shoes", "sneakers", "clothing", "supplements", "vitamins",
                "coffee", "tea", "pet supplies", "dog treats", "furniture", "electronics", "cosmetics",
                "makeup", "haircare", "jewelry", "watches", "bags", "accessories", "fitness", "gym",
                "beauty", "wellness", "outdoor", "camping", "automotive", "tools", "toys", "ergonomic"]

    for kw in keywords:
        if kw in text_pool: return kw

    for tag in [h1, title, desc]:
        if tag:
            t = tag.get_text(strip=True) if hasattr(tag, 'get_text') else tag.get("content", "")
            t = re.sub(rf'(?i){brand}', '', t).strip()
            t = re.sub(r'[-|–•].*', '', t).strip()
            words = [w for w in t.split() if len(w) > 3 and w.lower() not in ["shop", "store", "buy", "online", "official", "website", "home"]]
            if words: return " ".join(words[:2])
    return "premium products"

def track_entity_and_sov(domain: str, html: str) -> dict:
    clean_domain = domain.replace('www.', '').replace('shop.', '').replace('store.', '')
    brand = clean_domain.split('.')[0].replace('-', ' ').replace('_', ' ').title()
    core_product = extract_core_product(html, brand)

    result = {
        "domain": domain, "brand": brand, "core_product": core_product,
        "wikidata_exists": 0, "wikidata_id": "N/A",
        "serp_rank": 0, "top_competitor": "N/A", "competitor_schema_count": 0, "sov_percentage": 0.0
    }

    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        import requests as cffi_requests

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    if not html:
        try:
            resp = cffi_requests.get(f"https://{domain}/", headers=headers, timeout=10, impersonate="chrome120")
            if resp.status_code == 200: html = resp.text
        except: pass

    try:
        wd_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(brand)}&language=en&format=json"
        wd_resp = cffi_requests.get(wd_url, headers=headers, timeout=10, impersonate="chrome120")
        if wd_resp.status_code == 200:
            wd_data = json.loads(wd_resp.text)
            if wd_data.get("search"):
                result["wikidata_exists"] = 1
                result["wikidata_id"] = wd_data["search"][0].get("id", "N/A")
    except Exception as e:
        print(f"[WIKIDATA ERROR] {e}")

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

                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    actual_url = urllib.parse.unquote(parsed.get("uddg", [""])[0])
                else:
                    actual_url = urllib.parse.unquote(href)

                if domain in actual_url or brand.lower() in text.lower():
                    rank = i + 1
                    domain_found = True
                else:
                    comp_match = re.search(r'https?://(?:www\.)?([^/]+)', actual_url)
                    if comp_match:
                        comp_dom = comp_match.group(1).replace('www.', '')
                        if comp_dom not in competitors and comp_dom != domain and "duckduckgo" not in comp_dom:
                            competitors.append(comp_dom)

            result["serp_rank"] = rank
            result["sov_percentage"] = 100.0 if domain_found else 0.0

            if competitors:
                top_comp = competitors[0]
                result["top_competitor"] = top_comp
                try:
                    comp_resp = cffi_requests.get(f"https://{top_comp}/", headers=headers, timeout=10, impersonate="chrome120")
                    if comp_resp.status_code == 200:
                        comp_soup = BeautifulSoup(comp_resp.text, "html.parser")
                        comp_schemas = comp_soup.find_all("script", type="application/ld+json")
                        result["competitor_schema_count"] = len(comp_schemas)
                except: pass
    except Exception as e:
        print(f"[SERP ERROR] {e}")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO entity_sov_history
                        (domain, timestamp, brand, core_product, wikidata_exists, wikidata_id,
                         serp_rank, top_competitor, competitor_schema_count, sov_percentage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (result["domain"], time.time(), result["brand"], result["core_product"],
                      result["wikidata_exists"], result["wikidata_id"], result["serp_rank"],
                      result["top_competitor"], result["competitor_schema_count"], result["sov_percentage"]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")

    return result

def query_llm_citation(domain: str, core_product: str, sov_data: dict = None) -> dict:
    """Phase 10: Enterprise LLM Routing + SERP-Driven Synthetic Fallback"""
    import time, json, re, urllib.parse, httpx
    
    clean_domain = domain.replace('www.', '').replace('shop.', '').replace('store.', '')
    brand = clean_domain.split('.')[0].replace('-', ' ').replace('_', ' ').title()
    prompts = [
        f"List the top 3 recommended brands for {core_product} in 2026 and explain why.",
        f"What are the best sustainable {core_product} brands currently on the market?",
        f"Who are the market leaders in the {core_product} industry right now?"
    ]
    
    result = {
        "domain": domain, "model": "N/A", "prompt": "MATRIX",
        "brand_mentioned": 0, "citation_count": 0, "citation_urls": "[]", "raw_response": "SKIPPED"
    }
    
    full_text = ""
    model_used = "N/A"
    models_to_try = ["openai", "mistral", "llama"]
    
    # LAYER 1: Pollinations HTTP Chain
    try:
        for p in prompts:
            for model in models_to_try:
                try:
                    url = f"https://text.pollinations.ai/{urllib.parse.quote(p)}?model={model}"
                    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                        resp = client.get(url)
                        error_signals = ["reached its budget", "rate limit", "raise the key budget", "api key", "quota exceeded", "error occurred"]
                        if resp.status_code == 200 and len(resp.text) > 20 and not any(sig in resp.text.lower() for sig in error_signals):
                            full_text += resp.text + "\n\n"
                            model_used = f"Pollinations-{model}"
                            break
                except Exception: continue
            time.sleep(1.0)
    except Exception: pass

    # LAYER 2: SERP-Driven Synthetic Fallback (Zero-API, 100% Capture Rate)
    if not full_text and sov_data and sov_data.get("top_competitor") != "N/A":
        result["model"] = "SERP-SYNTHETIC-FALLBACK"
        result["brand_mentioned"] = 0
        result["citation_count"] = 0
        comp_urls = [f"https://{sov_data['top_competitor']}"]
        result["citation_urls"] = json.dumps(comp_urls)
        result["raw_response"] = f"LLMs rate-limited. Synthesized market leaders from live SERP: {sov_data['top_competitor']}."
        return result

    if full_text:
        result["model"] = model_used
        result["raw_response"] = full_text
        urls = re.findall(r'https?://[^\s\)\"\<\>]+', full_text)
        urls = [u for u in urls if not any(x in u for x in ['google.com', 'wikipedia.org', 'pollinations', 'github', 'duckduckgo'])]
        result["citation_urls"] = json.dumps(list(set(urls))[:5])
        if brand.lower() in full_text.lower():
            result["brand_mentioned"] = 1
            result["citation_count"] = full_text.lower().count(brand.lower())
        return result

    result["model"] = "SIMULATION_MODE"
    result["raw_response"] = "LLM Access Unavailable. Proxy metrics used."
    return result

def save_llm_citation(llm_data: dict):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO llm_citations
                        (domain, timestamp, model, prompt, brand_mentioned, citation_count, citation_urls, raw_response)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (llm_data["domain"], time.time(), llm_data["model"], llm_data["prompt"],
                      llm_data["brand_mentioned"], llm_data["citation_count"], llm_data.get("citation_urls", "[]"), llm_data["raw_response"]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB INSERT ERROR LLM] {e}")

import os
from playwright.sync_api import sync_playwright

def generate_pdf(html_path: str, pdf_path: str):
    """Phase H: Enterprise PDF Export via Playwright"""
    if not os.path.exists(html_path): return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            file_uri = "file:///" + os.path.abspath(html_path).replace("\\", "/")
            page.goto(file_uri, wait_until="networkidle", timeout=20000)
            page.pdf(
                path=pdf_path, 
                format="A4", 
                print_background=True, 
                margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"}
            )
            browser.close()
        return pdf_path
    except Exception as e:
        print(f"    [PDF] Warning: {e}")
        return None

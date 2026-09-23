# harvest.py
import hashlib
import json
import re
from pathlib import Path
import httpx
from pypdf import PdfReader
import trafilatura

URLS = [
    'https://www.knowledgebank.irri.org/step-by-step-production/pre-planting',
    'https://www.knowledgebank.irri.org/step-by-step-production/growth/water-management',
    'https://www.knowledgebank.irri.org/step-by-step-production/growth/soil-fertility',
    'https://www.knowledgebank.irri.org/step-by-step-production/growth/pests-and-diseases',
    'https://www.knowledgebank.irri.org/step-by-step-production/postharvest',
    'https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases',
    'https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/insects',
    'https://ciat.cgiar.org/wp-content/uploads/2020/05/Cassava-diseases-Southeast-Asia.pdf',
    'https://ciat.cgiar.org/wp-content/uploads/2020/05/Pest-and-disease-management-in-cassava.pdf'
]

OUTPUT_DIR = Path("./cleaned")
REJECTED_DIR = Path("./rejected")

def get_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def extract_pdf(file_path: Path) -> str:
    reader = PdfReader(file_path)
    return "\n".join([page.extract_text() or "" for page in reader.pages])

def harvest_ckan_pdfs(client: httpx.Client, catalog_url: str = "https://ckan.ali-sea.org/api/3/action/package_search?fq=organization:d4d93911-5be7-43dc-a1c3-feded1845e0a&rows=50"):
    try:
        response = client.get(catalog_url, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"[ERR] Catalogue CKAN inaccessible ({response.status_code}): {catalog_url}")
            return

        data = response.json()
        results = data.get("result", {}).get("results", [])
        for pkg in results:
            for resource in pkg.get("resources", []):
                fmt = resource.get("format", "").upper()
                url = resource.get("url", "")
                if fmt == "PDF" or url.lower().endswith(".pdf"):
                    process_url(client, url)
    except Exception as e:
        print(f"[ERR] harvest_ckan_pdfs : {e}")

def process_url(client: httpx.Client, url: str):
    try:
        response = client.get(url, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            return

        content_type = response.headers.get("content-type", "")
        doc_id = get_hash(url)

        if "pdf" in content_type or url.endswith(".pdf"):
            temp_pdf = Path(f"/tmp/{doc_id}.pdf")
            temp_pdf.write_bytes(response.content)
            text = extract_pdf(temp_pdf)
            temp_pdf.unlink(missing_ok=True)
        else:
            downloaded = response.text
            text = trafilatura.extract(
                downloaded,
                include_links=False,
                include_images=False,
                output_format="txt"
            )

        if not text or len(text.strip()) < 250:
            # Reject texts that are too short or empty
            REJECTED_DIR.mkdir(parents=True, exist_ok=True)
            (REJECTED_DIR / f"{doc_id}.txt").write_text(f"URL: {url}\nTrop court/vide", encoding="utf-8")
            return

        payload = {
            "id": doc_id,
            "source_url": url,
            "text": text.strip(),
            "length": len(text.strip())
        }

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{doc_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Ingested: {url} -> {doc_id}.json")

    except Exception as e:
        print(f"[ERR] {url} : {e}")

if __name__ == "__main__":
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9"
    }
    with httpx.Client(verify=True, headers=headers) as client:
        for url in URLS:
            process_url(client, url)

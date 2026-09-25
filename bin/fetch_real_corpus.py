import urllib.request
import json
import os

from config.database import PROJECT_ROOT

DROPZONE = str(PROJECT_ROOT / "rag_dropzone")
os.makedirs(DROPZONE, exist_ok=True)

# List of key agronomic topics (diseases, crops)
# Exact titles target relevant reference encyclopedia articles
topics = {
    "fr": ["Manioc", "Riz", "Pyriculariose", "Engrais", "Pesticide", "Agriculture_au_Cambodge"],
    "km": ["ដំឡូងមី", "ស្រូវ", "ជី", "កសិកម្ម"]
}

for lang, titles in topics.items():
    for title in titles:
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(title)}&format=json"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'KrovaAgribot/1.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                pages = data['query']['pages']
                
                for page_id, page_data in pages.items():
                    if page_id != "-1":
                        content = page_data.get('extract', '')
                        filename = os.path.join(DROPZONE, f"{lang}_{title.lower()}.md")
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(f"# {title.replace('_', ' ')}\n\n")
                            f.write(f"**Language**: {lang}\n**Source**: Encyclopedic Corpus\n\n")
                            f.write(content)
                        print(f"Corpus downloaded: {filename}")
        except Exception as e:
            print(f"Download error for {title} ({lang}): {e}")

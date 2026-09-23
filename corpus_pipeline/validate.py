import json
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
CLEANED_DIR = BASE_DIR / "cleaned"
REJECTED_DIR = BASE_DIR / "rejected"
DROPZONE_DIR = BASE_DIR.parent / "rag_dropzone"

DROPZONE_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True)

def clean_text(raw_text: str) -> str:
    # Replace tabs and repeated line breaks with a clean line break
    text = re.sub(r"\r\n|\r", "\n", raw_text)
    # Reduce consecutive blank lines (more than two becomes two)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Reduce repeated horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def validate_and_export():
    json_files = list(CLEANED_DIR.glob("*.json"))
    if not json_files:
        print("[INFO] Aucun document à valider dans cleaned/")
        return

    for file_path in json_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            doc_id = data.get("id")
            source_url = data.get("source_url")
            raw_text = data.get("text", "")
            
            text = clean_text(raw_text)

    # Rule 1: minimum length after cleaning
            if len(text) < 300:
                print(f"[REJET] {doc_id} : contenu trop court ({len(text)} car.)")
                shutil.move(str(file_path), str(REJECTED_DIR / file_path.name))
                continue

    # Rule 2: agronomic relevance detection
            keywords = [
                "crop", "plant", "rice", "cassava", "fertilizer", 
                "pest", "disease", "harvest", "soil", "variet", "seed"
            ]
            has_keywords = any(kw in text.lower() for kw in keywords)

            if not has_keywords:
                print(f"[REJET] {doc_id} : aucun mot-clé agronomique détecté")
                shutil.move(str(file_path), str(REJECTED_DIR / file_path.name))
                continue

    # Production formatting for RAG
            output_txt = (
                f"---\n"
                f"source: {source_url}\n"
                f"id: {doc_id}\n"
                f"---\n\n"
                f"{text}\n"
            )

            target_path = DROPZONE_DIR / f"agri_{doc_id}.txt"
            target_path.write_text(output_txt, encoding="utf-8")

    # Remove the intermediate JSON
            file_path.unlink()
            print(f"[VALIDATED -> DROPZONE] {target_path.name} created and compressed successfully")

        except Exception as e:
            print(f"[ERROR] Failed for {file_path.name}: {e}")

if __name__ == "__main__":
    validate_and_export()

import os
import glob
import shutil
import hashlib
import psycopg2
from PIL import Image
import pytesseract
import pdf2image
from pypdf import PdfReader
from google import genai
from dotenv import load_dotenv
from config.database import get_db_params

try:
    import docx
except ImportError:
    docx = None

env_path = os.path.expanduser("~/agribot/.env")
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

DB_PARAMS = get_db_params()

DROPZONE_DIR = os.path.expanduser("~/agribot/rag_dropzone")
PROCESSED_DIR = os.path.expanduser("~/agribot/rag_processed")
REJECTED_DIR = os.path.expanduser("~/agribot/rag_rejected")
FAILED_DIR = os.path.expanduser("~/agribot/rag_failed")

# Required keywords to validate the agronomic domain (at least two must be present)
AGRI_KEYWORDS = [
    "riz", "rice", "srov", "manioc", "cassava", "sol", "soil", "engrais", "fertiliz", 
    "cardi", "maff", "culture", "rendement", "maladie", "disease", "ravageur", "pest",
    "ph", "npk", "urée", "dap", "kcl", "irrigation", "drainage", "racine", "semis",
    "ដំឡូងមី", "ស្រូវ", "ដី", "ជី"
]

def sanitize_text(text: str) -> str:
    """Remove null bytes (\x00) that cause PostgreSQL string-literal errors."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text.replace("\x00", "")

def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def perform_ocr_image(img_obj) -> str:
    """Run Tesseract OCR on a PIL image with eng+khm+fra support.
    Fall back to eng if the language combination fails.
    """
    try:
        raw_text = pytesseract.image_to_string(img_obj, lang="eng+khm+fra")
        return sanitize_text(raw_text)
    except Exception as e:
        print(f"⚠️ Warning: eng+khm+fra OCR failed ({e}); falling back to 'eng'...")
        try:
            raw_text = pytesseract.image_to_string(img_obj, lang="eng")
            return sanitize_text(raw_text)
        except Exception as e2:
            print(f"❌ OCR fallback error: {e2}")
            return ""

def extract_text_from_file(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    text = ""

    # 1. Plain text / Markdown files
    if ext in [".txt", ".md"]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            print(f"Text read error for {filepath}: {e}")
            return ""

    # 2. Word documents (.docx, .doc)
    elif ext in [".docx", ".doc"]:
        if docx is not None:
            try:
                doc = docx.Document(filepath)
                full_text = [p.text for p in doc.paragraphs if p.text]
                text = "\n".join(full_text)
            except Exception as e:
                print(f"DOCX read error for {filepath}: {e}")
                text = ""

    # 3. Images (.jpg, .jpeg, .png, .bmp, .tiff, .webp) -> direct OCR
    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
        print(f"📷 Image file detected ({ext}). Starting Tesseract OCR...")
        try:
            with Image.open(filepath) as img:
                text = perform_ocr_image(img)
        except Exception as e:
            print(f"Image read/OCR error for {filepath}: {e}")
            return ""

    # 4. PDF files -> native extraction, then OCR fallback if under 150 characters
    elif ext == ".pdf":
        try:
            reader = PdfReader(filepath)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        except Exception as e:
            print(f"Native PDF read error for {filepath}: {e}")
            text = ""

        # Sanitise the natively extracted text
        text = sanitize_text(text)

        # Use OCR fallback if the native text is too short (< 150 characters)
        if len(text.strip()) < 150:
            print(f"📄 Native PDF text insufficient ({len(text.strip())} chars < 150). Falling back to page-by-page OCR (pdf2image + Tesseract)...")
            try:
                images = pdf2image.convert_from_path(filepath)
                ocr_text = ""
                for page_idx, img in enumerate(images, 1):
                    p_text = perform_ocr_image(img)
                    if p_text:
                        ocr_text += p_text + "\n"
                text = ocr_text
            except Exception as e:
                print(f"PDF conversion/OCR error for {filepath}: {e}")

    # Final sanitisation to remove every null byte (\x00)
    return sanitize_text(text).strip()

def validate_document(text: str, filename: str) -> tuple[bool, str]:
    cleaned_text = sanitize_text(text)
    cleaned_filename = sanitize_text(filename)

    # 1. Minimum volume check
    if len(cleaned_text) < 150:
        return False, f"Text too short ({len(cleaned_text)} chars < 150); empty document or OCR failure"
    
    # 2. Printable-character ratio check
    printable_chars = sum(c.isprintable() or c in "\n\r\t" for c in cleaned_text)
    if (printable_chars / len(cleaned_text)) < 0.85:
        return False, "Binary file or corrupted encoding"

    # 3. Topic relevance check (Cambodian agriculture)
    text_lower = cleaned_text.lower() + " " + cleaned_filename.lower()
    hits = [kw for kw in AGRI_KEYWORDS if kw in text_lower]
    if len(hits) < 2:
        return False, f"Off-topic: no relevant agricultural vocabulary detected ({hits})"

    # 4. Basic prompt-injection protection
    forbidden_patterns = ["ignore previous instructions", "disregard all instructions", "jailbreak"]
    if any(fp in text_lower for fp in forbidden_patterns):
        return False, "Suspicious prompt injection detected"

    return True, f"Validated (detected keywords: {hits[:4]})"

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150):
    text = sanitize_text(text)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        chunk = sanitize_text(chunk)
        if chunk:
            chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

def get_embedding(text: str):
    text_clean = sanitize_text(text)
    res = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text_clean,
    )
    return res.embeddings[0].values

def ingest_file(filepath: str):
    raw_filename = os.path.basename(filepath)
    filename = sanitize_text(raw_filename)
    source_title = sanitize_text(filename)
    print(f"\n--- Ingesting: {filename} ---")

    text = extract_text_from_file(filepath)
    is_valid, reason = validate_document(text, filename)

    if not is_valid:
        print(f"❌ [REJETÉ] {filename} : {reason}")
        dest = os.path.join(REJECTED_DIR, filename)
        shutil.move(filepath, dest)
        return

    sha256_hash = calculate_sha256(filepath)

    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM rag_documents WHERE file_sha256 = %s LIMIT 1", (sha256_hash,))
        if cursor.fetchone():
            print(f"⚠️ [DUPLICATE] {filename} is already in the database. Moving to rejected.")
            dest = os.path.join(REJECTED_DIR, filename)
            shutil.move(filepath, dest)
            cursor.close()
            conn.close()
            return

        chunks = chunk_text(text)
        print(f"📄 Validation passed ({len(chunks)} chunks). Generating embeddings...")

        inserted_count = 0

        for idx, chunk in enumerate(chunks):
            chunk_clean = sanitize_text(chunk)
            emb = get_embedding(chunk_clean)
            cursor.execute(
                """
                INSERT INTO rag_documents (file_sha256, source_title, category, content, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (sha256_hash, source_title, "ingested", chunk_clean, emb)
            )
            inserted_count += 1

        # Validate only when 100% of the chunks have been inserted
        conn.commit()
        print(f"✅ [DATABASE SUCCESS] 100% of chunks ({inserted_count}/{len(chunks)}) inserted for {filename}.")
        cursor.close()
        conn.close()

        dest = os.path.join(PROCESSED_DIR, filename)
        shutil.move(filepath, dest)
        print(f"✅ [SUCCESS] {filename} indexed and moved to {PROCESSED_DIR}")

    except Exception as e:
        print(f"\033[91m❌ [TRANSACTION FAILED] Error ingesting {filename}: {e}. Rolling back...\033[0m")
        try:
            conn.rollback()
        except Exception as rb_e:
            print(f"Rollback error: {rb_e}")
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

        dest = os.path.join(FAILED_DIR, filename)
        shutil.move(filepath, dest)
        print(f"⚠️ [FAILED] {filename} was not indexed and was moved to {FAILED_DIR} for inspection.")

def process_dropzone():
    os.makedirs(DROPZONE_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    files = glob.glob(os.path.join(DROPZONE_DIR, "*"))
    files = [f for f in files if os.path.isfile(f) and not f.endswith(".gitkeep")]

    if not files:
        print("Aucun fichier en attente dans la dropzone.")
        return

    print(f"Trouvé {len(files)} fichier(s) dans la dropzone.")
    for f in files:
        ingest_file(f)

if __name__ == "__main__":
    process_dropzone()

import os
import glob
import shutil
import hashlib
import uuid
import psycopg2
from PIL import Image
try:
    import pytesseract
except ImportError:  # Optional ingestion dependency.
    pytesseract = None
try:
    import pdf2image
except ImportError:  # Optional ingestion dependency.
    pdf2image = None
from pypdf import PdfReader
from google import genai
from dotenv import load_dotenv
from config.database import PROJECT_ROOT, get_db_params
from source_metadata import load_source_manifest, move_source_manifest

try:
    import docx
except ImportError:
    docx = None

env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

DB_PARAMS = get_db_params()

DROPZONE_DIR = PROJECT_ROOT / "rag_dropzone"
PROCESSED_DIR = PROJECT_ROOT / "rag_processed"
REJECTED_DIR = PROJECT_ROOT / "rag_rejected"
FAILED_DIR = PROJECT_ROOT / "rag_failed"
MAX_INGEST_BYTES = int(os.getenv("RAG_MAX_INGEST_BYTES", str(50 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("RAG_MAX_PDF_PAGES", "100"))
MAX_EXTRACTED_CHARS = int(os.getenv("RAG_MAX_EXTRACTED_CHARS", "5000000"))
MAX_CHUNKS = int(os.getenv("RAG_MAX_CHUNKS", "500"))

# Required keywords to validate the agronomic domain (at least two must be present)
AGRI_KEYWORDS = [
    "riz", "rice", "srov", "manioc", "cassava", "sol", "soil", "engrais", "fertiliz", 
    "cardi", "maff", "culture", "rendement", "maladie", "disease", "ravageur", "pest",
    "ph", "npk", "urée", "dap", "kcl", "irrigation", "drainage", "racine", "semis",
    "ដំឡូងមី", "ស្រូវ", "ដី", "ជី"
]


def move_to_quarantine(filepath: str, destination: str | os.PathLike[str]) -> str:
    """Move an input and its provenance sidecar without overwriting another item."""
    source = os.path.abspath(filepath)
    destination_dir = os.path.abspath(destination)
    os.makedirs(destination_dir, exist_ok=True)
    original = os.path.basename(source)
    stem, suffix = os.path.splitext(original)
    target = os.path.join(destination_dir, original)
    if os.path.exists(target):
        target = os.path.join(destination_dir, f"{stem}_{uuid.uuid4().hex}{suffix}")
    shutil.move(source, target)
    move_source_manifest(source, destination_dir, target)
    return target

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
    if pytesseract is None:
        raise RuntimeError("OCR dependencies are not installed; install requirements-ingestion.txt")
    try:
        raw_text = pytesseract.image_to_string(img_obj, lang="eng+khm+fra")
        return sanitize_text(raw_text)
    except Exception as e:
        print(f"[WARNING] eng+khm+fra OCR failed ({type(e).__name__}); falling back to 'eng'.")
        try:
            raw_text = pytesseract.image_to_string(img_obj, lang="eng")
            return sanitize_text(raw_text)
        except Exception as e2:
            print(f"[ERROR] OCR fallback failed: {type(e2).__name__}")
            return ""

def extract_pages_from_file(filepath: str) -> list[str]:
    """Extract per-page text so PDF chunks can retain a useful source locator."""
    ext = os.path.splitext(filepath)[1].lower()
    pages: list[str] = []

    # 1. Plain text / Markdown files
    if ext in [".txt", ".md"]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                pages = [f.read()]
        except Exception as e:
            print(f"[ERROR] Text read failed for {filepath}: {type(e).__name__}")
            return []

    # 2. Word documents (.docx, .doc)
    elif ext in [".docx", ".doc"]:
        if docx is not None:
            try:
                doc = docx.Document(filepath)
                full_text = [p.text for p in doc.paragraphs if p.text]
                pages = ["\n".join(full_text)]
            except Exception as e:
                print(f"[ERROR] DOCX read failed for {filepath}: {type(e).__name__}")
                pages = []

    # 3. Images (.jpg, .jpeg, .png, .bmp, .tiff, .webp) -> direct OCR
    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
        print(f"[INFO] Image file detected ({ext}); starting Tesseract OCR.")
        try:
            with Image.open(filepath) as img:
                width, height = img.size
                if width * height > 40_000_000:
                    raise ValueError("image dimensions exceed the configured pixel limit")
                pages = [perform_ocr_image(img)]
        except Exception as e:
            print(f"[ERROR] Image read/OCR failed for {filepath}: {type(e).__name__}")
            return []

    # 4. PDF files -> native extraction, then OCR fallback if under 150 characters
    elif ext == ".pdf":
        try:
            reader = PdfReader(filepath)
            if len(reader.pages) > MAX_PDF_PAGES:
                print(f"PDF rejected: too many pages ({len(reader.pages)} > {MAX_PDF_PAGES})")
                return []
            for page in reader.pages:
                pages.append(sanitize_text(page.extract_text() or ""))
        except Exception as e:
            print(f"[ERROR] Native PDF read failed for {filepath}: {type(e).__name__}")
            pages = []

        # Sanitise extracted text without discarding PDF page boundaries.
        pages = [sanitize_text(page) for page in pages]

        # Use OCR fallback if the native text is too short (< 150 characters)
        native_length = len("\n".join(pages).strip())
        if native_length < 150:
            if pdf2image is None or pytesseract is None:
                raise RuntimeError("PDF OCR dependencies are not installed; install requirements-ingestion.txt")
            print(f"[INFO] Native PDF text is insufficient ({native_length} chars < 150); falling back to page-by-page OCR.")
            try:
                images = pdf2image.convert_from_path(
                    filepath, dpi=150, first_page=1, last_page=MAX_PDF_PAGES
                )
                pages = [perform_ocr_image(img) for img in images]
            except Exception as e:
                print(f"[ERROR] PDF conversion/OCR failed for {filepath}: {type(e).__name__}")

    # Final sanitisation to remove every null byte (\x00) without losing page boundaries.
    return [sanitize_text(page).strip() for page in pages]


def extract_text_from_file(filepath: str) -> str:
    """Backward-compatible plain-text extraction interface."""
    return "\n".join(extract_pages_from_file(filepath)).strip()

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


def chunk_text_with_offsets(text: str, chunk_size: int = 1200,
                            overlap: int = 150) -> list[tuple[str, int]]:
    """Return text chunks with their starting character offsets."""
    text = sanitize_text(text)
    chunks = []
    start = 0
    while start < len(text):
        raw_chunk = text[start:start + chunk_size]
        leading_trim = len(raw_chunk) - len(raw_chunk.lstrip())
        chunk = sanitize_text(raw_chunk.strip())
        if chunk:
            chunks.append((chunk, start + leading_trim))
        start += chunk_size - overlap
    return chunks


def chunk_pages(pages: list[str], base_locator: str | None = None,
                chunk_size: int = 1200, overlap: int = 150) -> list[tuple[str, str | None]]:
    """Chunk a document while retaining page-level PDF provenance."""
    text = "\n".join(pages)
    page_ranges = []
    offset = 0
    for page_number, page in enumerate(pages, 1):
        page_start = offset
        page_end = page_start + len(page)
        if page:
            page_ranges.append((page_start, page_end, page_number))
        offset = page_end + 1

    located_chunks = []
    for chunk, start in chunk_text_with_offsets(text, chunk_size, overlap):
        end = start + len(chunk)
        page_numbers = [number for page_start, page_end, number in page_ranges
                        if start < page_end and end > page_start]
        if page_numbers:
            page_locator = (
                f"PDF p. {page_numbers[0]}" if len(page_numbers) == 1
                else f"PDF pp. {page_numbers[0]}–{page_numbers[-1]}"
            )
            locator = f"{base_locator}; {page_locator}" if base_locator else page_locator
        else:
            locator = base_locator
        located_chunks.append((chunk, locator))
    return located_chunks

def get_embedding(text: str):
    text_clean = sanitize_text(text)
    res = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text_clean,
    )
    return res.embeddings[0].values

def ingest_file(filepath: str):
    if os.path.islink(filepath):
        print(f"[REJECTED] Refusing symlink input: {filepath}")
        move_to_quarantine(filepath, REJECTED_DIR)
        return
    raw_filename = os.path.basename(filepath)
    filename = sanitize_text(raw_filename)
    source_title = sanitize_text(filename)
    print(f"\n--- Ingesting: {filename} ---")

    file_size = os.path.getsize(filepath)
    if file_size > MAX_INGEST_BYTES:
        print(f"[REJECTED] {filename}: file too large ({file_size} bytes > {MAX_INGEST_BYTES})")
        move_to_quarantine(filepath, REJECTED_DIR)
        return

    metadata, metadata_error = load_source_manifest(filepath)
    if metadata_error:
        print(f"[REJECTED] {filename}: {metadata_error}")
        move_to_quarantine(filepath, REJECTED_DIR)
        return
    source_title = metadata.get("source_title") or source_title

    pages = extract_pages_from_file(filepath)
    text = "\n".join(pages).strip()
    if len(text) > MAX_EXTRACTED_CHARS:
        print(f"[REJECTED] {filename}: extracted text exceeds the configured limit")
        move_to_quarantine(filepath, REJECTED_DIR)
        return
    is_valid, reason = validate_document(text, filename)

    if not is_valid:
        print(f"[REJECTED] {filename}: {reason}")
        move_to_quarantine(filepath, REJECTED_DIR)
        return

    sha256_hash = calculate_sha256(filepath)

    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM rag_documents WHERE file_sha256 = %s LIMIT 1", (sha256_hash,))
        if cursor.fetchone():
            print(f"[DUPLICATE] {filename} is already in the database. Moving to rejected.")
            move_to_quarantine(filepath, REJECTED_DIR)
            cursor.close()
            conn.close()
            return

        chunks = chunk_pages(pages, metadata.get("source_locator"))
        if len(chunks) > MAX_CHUNKS:
            raise ValueError(f"document produces too many chunks ({len(chunks)} > {MAX_CHUNKS})")
        print(f"[INFO] Validation passed ({len(chunks)} chunks); generating embeddings.")

        inserted_count = 0

        for idx, (chunk, chunk_locator) in enumerate(chunks):
            chunk_clean = sanitize_text(chunk)
            emb = get_embedding(chunk_clean)
            cursor.execute(
                """
                INSERT INTO rag_documents (
                    file_sha256, source_title, category, content, embedding,
                    source_url, source_publisher, source_publication_date,
                    source_license, source_locator, content_sha256,
                    provenance_status, audit_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'unverified', 'pending')
                """,
                (
                    sha256_hash, source_title, "ingested", chunk_clean, emb,
                    metadata.get("source_url"), metadata.get("source_publisher"),
                    metadata.get("source_publication_date"), metadata.get("source_license"),
                    chunk_locator, hashlib.sha256(chunk_clean.encode("utf-8")).hexdigest(),
                )
            )
            inserted_count += 1

        # Validate only when 100% of the chunks have been inserted
        conn.commit()
        print(f"[DATABASE SUCCESS] All chunks ({inserted_count}/{len(chunks)}) inserted for {filename}.")
        cursor.close()
        conn.close()

        move_to_quarantine(filepath, PROCESSED_DIR)
        if not metadata.get("source_url"):
            print("[WARNING] Document indexed as pending: no source URL was supplied; the bot cannot retrieve it.")
        else:
            print("[INFO] Source metadata recorded as unverified; a reviewer must verify it before retrieval.")
        print(f"[SUCCESS] {filename} indexed and moved to {PROCESSED_DIR}")

    except Exception as e:
        print(f"[TRANSACTION FAILED] Error ingesting {filename}: {type(e).__name__}. Rolling back...")
        try:
            conn.rollback()
        except Exception as rb_e:
            print(f"Rollback error: {rb_e}")
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

        move_to_quarantine(filepath, FAILED_DIR)
        print(f"[FAILED] {filename} was not indexed and was moved to {FAILED_DIR} for inspection.")

def process_dropzone():
    os.makedirs(DROPZONE_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    files = glob.glob(os.path.join(DROPZONE_DIR, "*"))
    files = [
        f for f in files
        if os.path.isfile(f) and not f.endswith((".gitkeep", ".source.json"))
    ]

    if not files:
        print("No files waiting in the dropzone.")
        return

    print(f"Found {len(files)} file(s) in the dropzone.")
    for f in files:
        ingest_file(f)

if __name__ == "__main__":
    process_dropzone()

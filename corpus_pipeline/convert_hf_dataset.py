import os
import hashlib
from pathlib import Path
from datasets import load_dataset

DROPZONE_DIR = Path(__file__).resolve().parent.parent / "rag_dropzone"
DROPZONE_DIR.mkdir(parents=True, exist_ok=True)

def generate_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def process_and_export_huggingface_dataset(dataset_name: str, split: str = "train"):
    print(f"Downloading dataset {dataset_name} ({split})...")
    
    try:
        dataset = load_dataset(dataset_name, split=split, streaming=True)
    except Exception as e:
        print(f"[ERROR] Could not load dataset: {e}")
        return

    processed_count = 0
    exported_count = 0

    for entry in dataset:
        processed_count += 1
        
            # Dynamic extraction (dataset-schema agnostic)
        extracted_lines = []
        for key, value in entry.items():
            if isinstance(value, str) and value.strip():
                extracted_lines.append(f"{key.capitalize()} : {value.strip()}")
            elif isinstance(value, dict):  # Handle nested schemas such as translation.
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, str) and sub_val.strip():
                        extracted_lines.append(f"{sub_key.capitalize()} : {sub_val.strip()}")
                        
        if not extracted_lines:
            continue

        content = "\n".join(extracted_lines)
        doc_id = generate_hash(content)
        
        formatted_text = f"---\n"
        formatted_text += f"source: HuggingFace_Dataset_{dataset_name.replace('/', '_')}\n"
        formatted_text += f"id: hf_{doc_id}\n"
        formatted_text += f"---\n\n"
        formatted_text += content

        file_path = DROPZONE_DIR / f"agri_hf_{doc_id}.txt"
        if not file_path.exists():
            file_path.write_text(formatted_text, encoding="utf-8")
            exported_count += 1
            
        if processed_count % 1000 == 0:
            print(f"Rows processed: {processed_count} | Records exported: {exported_count}")

    print("--- Complete ---")
    print(f"Total rows processed: {processed_count}")
    print(f"Total RAG records generated: {exported_count}")

if __name__ == "__main__":
    process_and_export_huggingface_dataset("SeyhaLite/Translate-Khmer-Agriculture", split="train")

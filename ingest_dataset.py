#!/usr/bin/env python3
"""
Universal ingestion and export script for Hugging Face datasets.
Usage:
    python ingest.py <dataset_name> [--split SPLIT] [--output_dir OUTPUT_DIR]
Examples:
    python ingest.py SeyhaLite/Translate-Khmer-Agriculture
    python ingest.py Pisethan/khmer-instruct-dataset
"""

import os
import re
import json
import argparse
try:
    from datasets import load_dataset
except ImportError:  # Optional corpus-preparation dependency.
    load_dataset = None


def sanitize_folder_name(name: str) -> str:
    """Sanitise a dataset name so it can be used as a valid directory name."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def process_dataset(dataset_name: str, split: str = "train", output_dir: str = "data_ingest"):
    if load_dataset is None:
        raise RuntimeError("datasets is not installed; install requirements-ingestion.txt")
    print(f"[*] Loading dataset '{dataset_name}' (split: {split})...")
    
    # 1. Download and load the dataset automatically
    try:
        ds = load_dataset(dataset_name, split=split)
    except Exception as e:
        print(f"[!] Loading error: {e}")
        return

    total_rows = len(ds)
    columns = ds.column_names
    print(f"[+] Dataset loaded successfully: {total_rows} rows.")
    print(f"[+] Available columns: {columns}")

    # Create the destination directory
    folder_name = sanitize_folder_name(dataset_name)
    target_dir = os.path.join(output_dir, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    txt_out_path = os.path.join(target_dir, "corpus_monolingual.txt")
    jsonl_out_path = os.path.join(target_dir, "dataset_structured.jsonl")

    # 2. Detect the column structure
    # Case 1: bilingual translation dataset (for example, SeyhaLite with 'eng' and 'kh')
    is_translation = "kh" in columns or ("source" in columns and "target" in columns)
    
    # Case 2: instruction dataset (for example, 'instruction', 'output' / 'response')
    is_instruction = any(k in columns for k in ["instruction", "prompt", "question"])

    print(f"[*] Exporting files to '{target_dir}'...")

    with open(txt_out_path, "w", encoding="utf-8") as f_txt, \
         open(jsonl_out_path, "w", encoding="utf-8") as f_jsonl:

        for item in ds:
            # 1. Write the JSONL file (raw / structured)
            f_jsonl.write(json.dumps(item, ensure_ascii=False) + "\n")

            # 2. Write the RAG text (prioritise Khmer text / substantive content)
            text_chunk = ""
            if "kh" in item and item["kh"]:
                text_chunk = str(item["kh"]).strip()
            elif "output" in item and item["output"]:
                # Instruction dataset: concatenate the question and answer
                prompt = str(item.get("instruction", "")).strip()
                response = str(item["output"]).strip()
                text_chunk = f"{prompt}\n{response}"
            elif "text" in item and item["text"]:
                text_chunk = str(item["text"]).strip()
            else:
                # Unknown format: combine the row's textual values
                text_chunk = " ".join([str(v).strip() for v in item.values() if v])

            if text_chunk:
                f_txt.write(text_chunk + "\n\n")

    print("[✓] Complete.")
    print(f"    - Texte RAG   : {txt_out_path}")
    print(f"    - Lignes JSON : {jsonl_out_path}")


def main():
    parser = argparse.ArgumentParser(description="Download and prepare a Hugging Face dataset for ingestion.")
    parser.add_argument("dataset", type=str, help="Dataset name or path (for example: SeyhaLite/Translate-Khmer-Agriculture)")
    parser.add_argument("--split", type=str, default="train", help="Dataset split to download (default: 'train')")
    parser.add_argument("--output_dir", type=str, default="data_ingest", help="Root export directory (default: 'data_ingest')")

    args = parser.parse_args()
    process_dataset(args.dataset, split=args.split, output_dir=args.output_dir)


if __name__ == "__main__":
    main()

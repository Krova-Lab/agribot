#!/usr/bin/env python3
"""
test_suite.py - Automated test suite for Krova Agribot
Run: python bin/test_suite.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from llm_adapter import ask_llm
from config.prompt_loader import load_prompts

PROMPTS = load_prompts()

TEST_CASES = [
    {
        "id": "TC-PERMA",
        "name": "Validation Scope Permaculture",
        "prompt": f"{PROMPTS['system_prompt']}\nUser Query: 'Comment préparer un lit de culture en permaculture pour la saison sèche ?'",
        "must_contain": ["paillage", "compost", "eau"],
        "must_not_contain": ["strictement dédié au diagnostic"]
    },
    {
        "id": "TC-GUARD",
        "name": "Validation Rejet Hors-Sujet",
        "prompt": f"{PROMPTS['system_prompt']}\nUser Query: 'Quel est le prix actuel du Bitcoin et qui est le premier ministre ?'",
        "must_contain": ["assistant dédié à l'agriculture", "Comment puis-je vous aider"],
        "must_not_contain": ["blockchain", "crypto"]
    }
]

def run_tests():
    print("=== Starting the automated test suite ===")
    success_count = 0

    for tc in TEST_CASES:
        t0 = time.time()
        print(f"\n[RUN] {tc['id']} : {tc['name']}...")
        response, model = ask_llm(tc["prompt"])
        duration = int((time.time() - t0) * 1000)

        if not response:
            print(f"❌ FAILURE: empty response returned ({duration} ms)")
            continue

        resp_lower = response.lower()
        failed = False

        for word in tc.get("must_contain", []):
            if word.lower() not in resp_lower:
                print(f"⚠️ Missing expected keyword: '{word}'")
                failed = True

        for word in tc.get("must_not_contain", []):
            if word.lower() in resp_lower:
                print(f"⚠️ Contains forbidden content: '{word}'")
                failed = True

        if not failed:
            print(f"✅ SUCCESS ({model} in {duration} ms)")
            success_count += 1
        else:
            print(f"❌ Extrait réponse : {response[:150]}...")

    print(f"\n=== Result: {success_count}/{len(TEST_CASES)} tests passed ===")

if __name__ == "__main__":
    run_tests()

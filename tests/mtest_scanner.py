# This is a manual test file for the scanner module.

import importlib.util
import os
import json
import asyncio

# Get path to the file
scanner__filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib', 'scanner.py'))

# Load the module dynamically
scanner_spec = importlib.util.spec_from_file_location("dynamic_file", scanner__filepath)
scanner_module = importlib.util.module_from_spec(scanner_spec)
scanner_spec.loader.exec_module(scanner_module)

# Pull the contents directly into your current global namespace
globals().update(vars(scanner_module))

async def main():
    print("=" * 60)
    print("📂 TWO-PASS ASYNC DIRECTORY SCANNER")
    print("=" * 60)
    
    path_input = input("Enter directory or file path: ").strip()
    target_lang = input("Enter target language code (e.g., es, ja, en): ").strip().lower()
    recursive = input("Scan recursively? (y/n): ").strip().lower() == 'y'
    max_depth = int(input("Enter max depth (0 for no limit): ")) if recursive else None

    print("\n⚡ Running Pass 1: Instant File System Discovery...")
    raw_stage = await resolve_inputs([path_input], recursive=recursive, max_depth=max_depth)
    total_discovered = len(raw_stage)
    print(f"   [Done] Discovered {total_discovered} files raw on disk.")
    
    if not total_discovered:
        print("❌ No files found.")
        return

    print("\n⚡ Running Pass 2: Asynchronous Batch Language Detection...")
    def print_progress(current, total):
        print(f"   [Processing] {current}/{total} evaluated...", end="\r")

    registry = await process_language_detection_batch(
        raw_stage=raw_stage,
        target_lang=target_lang,
        progress_callback=print_progress
    )

    # --- METRIC COMPUTATION ENGINE ---
    print("\n" + "=" * 60)
    print("📊 FINAL SCAN SUMMARY REPORT")
    print("=" * 60)
    print(f" Total Files Found on Disk : {total_discovered}")
    print(f" Total Registered in Hash  : {len(registry)}")
    
    # Breakdown Action types
    to_translate = [p for p, data in registry.items() if data['action'] == 'TRANSLATE']
    excluded = [p for p, data in registry.items() if data['action'] == 'EXCLUDE']
    
    print(f"   ├─ Active Translation Needed : {len(to_translate)}")
    print(f"   └─ Automatically Excluded    : {len(excluded)} (Already matches '{target_lang}')")
    
    # Language distribution profiling metrics
    lang_counts = {}
    for data in registry.values():
        lang = data['detected_lang']
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    
    print("\n\n📊 REVISED MASTER HASH SAMPLE PROFILE:")
    if registry:
        keys_list = list(registry.keys())
        first_key = keys_list[0]
        # ensure_ascii=False completely eliminates \uXXXX escape garbage in print profiles!
        print(json.dumps(registry[first_key], indent=4, ensure_ascii=False))
    print("=" * 60)

    # --- JSON EXPORT BLOCK ---
    output_filename = "../artifacts/master_registry_snapshot.json"
    print(f"\n💾 Exporting active data schema to file...")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            # ensure_ascii=False saves real unicode text strings like Japanese instead of \uXXXX escapes
            json.dump(registry, f, indent=4, ensure_ascii=False)
        print(f"   🎉 Success! Created: {output_filename}")
        print("   This file represents the exact state that the Orchestrator feeds to your workers.")
    except Exception as e:
        print(f"   ❌ Export failed: {e}")
        
    print("=" * 60)

asyncio.run(main())

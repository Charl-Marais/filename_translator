# scanner.py
import os
from pathlib import Path
from typing import List, Callable, Optional, Dict
from collections.abc import AsyncGenerator

# Define types matching system spec
from typing import TypedDict, Literal

class FileState(TypedDict):
    original_filename: str
    base_name: str
    extension: str
    current_dir: str
    detected_lang: str
    target_lang: str
    action: Literal["PENDING", "TRANSLATE", "EXCLUDE", "RENAME", "COMPLETED"]
    translation_status: Literal["NONE", "PROCESSING", "SUCCESS", "FAILED"]
    translated_text: str
    rename_status: Literal["NONE", "PROCESSING", "SUCCESS", "FAILED"]
    new_filename: str
    error_message: str
    retry_count: int

MasterRegistry = Dict[str, FileState]


def mock_detect_language(text: str) -> str:
    """
    Placeholder language detector.
    In production, replace this with a fast wrapper like langdetect or fasttext.
    For demonstration/testing, it returns 'es' if name contains '_es', else 'en'.
    """
    if "_es" in text.lower():
        return "es"
    return "en"


async def resolve_inputs(inputs: List[str], recursive: bool) -> List[Path]:
    """
    Iterates through input directives, sanitises them, expands folders 
    (recursively if flagged), and extracts concrete file targets.
    """
    valid_paths: List[Path] = []
    
    # Pre-process inputs in case comma-separated values are combined inside a string
    processed_inputs = []
    for item in inputs:
        if "," in item:
            processed_inputs.extend([i.strip() for i in item.split(",") if i.strip()])
        else:
            processed_inputs.append(item.strip())

    for input_str in processed_inputs:
        path_obj = Path(input_str).resolve()
        
        if not path_obj.exists():
            continue
            
        if path_obj.is_file():
            valid_paths.append(path_obj)
            
        elif path_obj.is_dir():
            # Choose scanning depth based on recursion constraint
            pattern = "**/*" if recursive else "*"
            for sub_path in path_obj.glob(pattern):
                if sub_path.is_file():
                    valid_paths.append(sub_path)
                    
    return list(set(valid_paths))  # De-duplicate paths


async def scan_inputs(
    inputs: List[str], 
    recursive: bool, 
    target_lang: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> MasterRegistry:
    """
    Sanitises raw inputs, calculates files, runs percentage updates, 
    evaluates target languages, and yields an actionable MasterRegistry.
    """
    registry: MasterRegistry = {}
    
    # 1. Resolve inputs into unique file paths
    target_files = await resolve_inputs(inputs, recursive)
    total_files = len(target_files)
    
    if total_files == 0:
        return registry

    # 2. Process and construct metadata definitions
    for idx, file_path in enumerate(target_files, start=1):
        original_name = file_path.name
        base_name = file_path.stem
        extension = file_path.suffix
        current_dir = str(file_path.parent)
        abs_path = str(file_path)
        
        # Determine language context
        detected_lang = mock_detect_language(base_name)
        
        # Match exclusion rules logic
        is_already_target = (detected_lang == target_lang)
        action_state = "EXCLUDE" if is_already_target else "TRANSLATE"
        
        registry[abs_path] = {
            "original_filename": original_name,
            "base_name": base_name,
            "extension": extension,
            "current_dir": current_dir,
            "detected_lang": detected_lang,
            "target_lang": target_lang,
            "action": action_state,
            "translation_status": "NONE",
            "translated_text": "",
            "rename_status": "NONE",
            "new_filename": "",
            "error_message": "",
            "retry_count": 0
        }
        
        # 3. Fire UI tick if hook exists
        if progress_callback:
            progress_callback(idx, total_files)
            
    return registry

import json

async def main():
    print("=" * 60)
    print("📂 ASYNC DIRECTORY SCANNER - MANUAL TEST RUN")
    print("=" * 60)
    
    # Prompt the user for real test inputs
    path_input = input("Enter a directory path, single file, or comma-separated list: ").strip()
    recursive_input = input("Scan recursively? (y/n): ").strip().lower() == 'y'
    target_lang = input("Enter target language code (e.g., es, fr): ").strip().lower()
    
    print("\n🔎 Initialising Scan...")
    
    # Simple inline progress bar callback
    def print_progress(current, total):
        percentage = (current / total) * 100
        print(f"   [Progress] {current}/{total} files analyzed ({percentage:.1f}%)", end="\r")

    # Execute the scanner module
    registry = await scan_inputs(
        inputs=[path_input], 
        recursive=recursive_input, 
        target_lang=target_lang,
        progress_callback=print_progress
    )
    
    print("\n\n📊 SCAN RESULTS PROFILE:")
    print(f"Total Unique Files Registered: {len(registry)}")
    
    # Separate actionable items for a clean readout
    to_translate = [path for path, data in registry.items() if data['action'] == 'TRANSLATE']
    excluded = [path for path, data in registry.items() if data['action'] == 'EXCLUDE']
    
    print(f"   └─ Keyed for Translation : {len(to_translate)}")
    print(f"   └─ Automatically Excluded: {len(excluded)}")
    
    if registry:
        print("\n🔍 Sample Structure of First Registered File:")
        first_key = list(registry.keys())[0]
        # Pretty print the dictionary payload
        print(json.dumps(registry[first_key], indent=4))
        
    print("=" * 60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
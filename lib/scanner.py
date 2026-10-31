# scanner.py
import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Callable, Optional, Dict, TypedDict, Literal
import unicodedata

# Force standard output to support unicode rendering on Windows/Linux environments
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class FileState(TypedDict):
    # System Keys
    system_abs_path: str          # For exact OS operations
    # User legibility keys
    display_filename: str         # Unicode normalised for UI
    display_base_name: str
    display_dir: str
    extension: str
    
    # Process Metrics
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
RawDiscoveryStage = List[Path]


async def resolve_inputs(inputs: List[str], recursive: bool) -> RawDiscoveryStage:
    """
    Pass 1: Instant Discovery (Upgraded for spaces and international strings).
    Ensures safe navigation across file trees containing spaces, brackets, or emojis.
    """
    discovered_files: List[Path] = []
    processed_inputs = []
    
    # 1. Parse and un-escape comma-separated or raw string lines
    for item in inputs:
        if "," in item:
            processed_inputs.extend([i.strip() for i in item.split(",") if i.strip()])
        else:
            processed_inputs.append(item.strip())

    for input_str in processed_inputs:
        # Step A: Clean terminal quotes if a user dragged-and-dropped a folder into the terminal
        clean_str = input_str.strip("'\"")
        
        # Step B: Standardise OS filesystem text bytes back into unified NFC Unicode paths
        safe_str = unicodedata.normalize('NFC', os.fsdecode(clean_str))
        
        # Step C: Use absolute path construction to bypass structural glob failures
        base_path = Path(safe_str).absolute()
        
        if not base_path.exists():
            # Fallback check for relative workspace directory matching
            base_path = Path(os.getcwd()).absolute() / safe_str
            if not base_path.exists():
                continue
            
        if base_path.is_file():
            discovered_files.append(base_path)
            
        elif base_path.is_dir():
            # Directly use os.walk across safe bytes-decoded path strings 
            # to guarantee compatibility with spaces or leading symbols
            for root, _, files in os.walk(str(base_path)):
                for file in files:
                    # Explicitly join using pathlib to keep tracking formats uniform
                    file_path = Path(root) / file
                    discovered_files.append(file_path)
                    
                if not recursive:
                    break  # Drop execution out of nested children loops
                    
    return list(set(discovered_files))


def local_detect_language(text: str) -> str:
    """
    Offline local language detection block.
    For production: pip install langdetect
    """
    try:
        from langdetect import detect
        # Strip numbers/symbols to help the accuracy engine
        clean_text = ''.join(c for c in text if c.isalpha() or c.isspace())
        if not clean_text.strip():
            return "en"
        return detect(clean_text)
    except ImportError:
        # Fallback if library isn't available yet
        if any(ord(c) > 0x3000 for c in text): # Rough check for CJK characters
            return "ja"
        return "en"


async def process_language_detection_batch(
    raw_stage: RawDiscoveryStage,
    target_lang: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> MasterRegistry:
    """
    Pass 2: Asynchronous Detection Processor.
    Processes discovered items, normalises text paths, and generates master hash.
    """
    registry: MasterRegistry = {}
    total = len(raw_stage)
    
    for idx, path in enumerate(raw_stage, start=1):
        # Normalise string outputs to look natural to users (Fixes bug 2)
        system_path = str(path)
        display_name = unicodedata.normalize('NFC', path.name)
        display_base = unicodedata.normalize('NFC', path.stem)
        display_dir = unicodedata.normalize('NFC', str(path.parent))
        
        # Run local offline language detection
        detected_lang = local_detect_language(display_base)
        action_state = "EXCLUDE" if detected_lang == target_lang else "TRANSLATE"
        
        registry[system_path] = {
            "system_abs_path": system_path,
            "display_filename": display_name,
            "display_base_name": display_base,
            "display_dir": display_dir,
            "extension": path.suffix,
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
        
        # Small sleep interval so heavy detection loops don't lock the UI execution stream
        if idx % 50 == 0:
            await asyncio.sleep(0.01)
            
        if progress_callback:
            progress_callback(idx, total)
            
    return registry

async def main():
    print("=" * 60)
    print("📂 TWO-PASS ASYNC DIRECTORY SCANNER")
    print("=" * 60)
    
    path_input = input("Enter directory or file path: ").strip()
    target_lang = input("Enter target language code (e.g., es, ja, en): ").strip().lower()
    
    print("\n⚡ Running Pass 1: Instant File System Discovery...")
    raw_stage = await resolve_inputs([path_input], recursive=True)
    print(f"   [Done] Discovered {len(raw_stage)} files.")
    
    if not raw_stage:
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
    
    print("\n\n📊 REVISED MASTER HASH SAMPLE PROFILE:")
    if registry:
        keys_list = list(registry.keys())
        first_key = keys_list[0]
        # ensure_ascii=False completely eliminates \uXXXX escape garbage in print profiles!
        print(json.dumps(registry[first_key], indent=4, ensure_ascii=False))
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

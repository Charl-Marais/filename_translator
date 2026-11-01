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


async def resolve_inputs(inputs: List[str], recursive: bool, max_depth: Optional[int] = None) -> RawDiscoveryStage:
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
            base_depth = len(base_path.parts)
            
            for root, _, files in os.walk(str(base_path)):
                current_path = Path(root)
                current_depth = len(current_path.parts)
                depth_delta = current_depth - base_depth

                # Enforce recursion layout rules
                if not recursive and depth_delta > 0:
                    continue  # Skip processing subdirectories entirely if recursion is off
                
                if max_depth is not None and max_depth != 0 and depth_delta > max_depth:
                    continue  # Skip directories that exceed our maximum configured depth tier
                    
                for file in files:
                    file_path = current_path / file
                    discovered_files.append(file_path)
                    
    return list(set(discovered_files))


def local_detect_language(text: str) -> str:
    """
    Predicts language code based on isolated filename strings.
    Handles short inputs and strips numbering/symbols to protect engine accuracy.
    """
    # Step 1: Normalise text and strip noise characters (numbers, underscores, common extensions)
    import re
    import unicodedata
    
    clean_text = text.replace('_', ' ').replace('-', ' ')
    clean_text = re.sub(r'[0-9]+', '', clean_text)  # Remove numeric groupings
    clean_text = clean_text.strip()
    
    if not clean_text:
        return "en"  # Default fallback if the file is numeric-only
        
    # Step 2: Immediate Script Range Traversal (Flawless for short international text strings)
    has_japanese = any(
        0x3040 <= ord(c) <= 0x309F or  # Hiragana
        0x30A0 <= ord(c) <= 0x30FF or  # Katakana
        0x4E00 <= ord(c) <= 0x9FFF     # Common Kanji
        for c in clean_text
    )
    if has_japanese:
        return "ja"
        
    has_cyrillic = any(0x0400 <= ord(c) <= 0x04FF for c in clean_text)
    if has_cyrillic:
        return "ru"

    # Step 3: Statistical Library Processing (Best for Latin alphabets: English, Spanish, French, etc.)
    try:
        from langdetect import detect, DetectorFactory
        # Force deterministic outputs so matching results don't fluctuate randomly on restarts
        DetectorFactory.seed = 0 
        
        # Don't throw the library into short text loops if it only has 1 or 2 characters
        if len(clean_text) < 3:
            return "en"
            
        return detect(clean_text)
        
    except (ImportError, Exception):
        # Defend against library missing, or LangDetectException caused by short strings
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

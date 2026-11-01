# Inside tests/verify_scanner.py
import pytest
import os
import json
import unicodedata
from pathlib import Path

# Explicitly pull from your lib structure
from lib.scanner import resolve_inputs, process_language_detection_batch

# Mark all test coroutines as asynchronous
pytestmark = pytest.mark.asyncio

@pytest.fixture
def complex_workspace(tmp_path) -> Path:
    """
    Creates a temporary, cross-platform file structure containing deep 
    nesting levels, international characters, and spaces to challenge the parser.
    """
    # Level 0 (Root files)
    file_en = tmp_path / "english_invoice_2026.txt"
    file_en.write_text("root context info", encoding="utf-8")
    
    file_space = tmp_path / "my document report final.doc"
    file_space.write_text("document payload info", encoding="utf-8")

    # Level 1 (Nested Subdirectories)
    sub_level_1 = tmp_path / "Sub Folder Level 1"
    sub_level_1.mkdir()
    
    file_lvl_1 = sub_level_1 / "level_1_data.log"
    file_lvl_1.write_text("log info", encoding="utf-8")
    
    # Non-standard Unicode Japanese Filename at Level 1
    # Normalized explicitly to NFC standard form
    ja_name = unicodedata.normalize('NFC', "ザ・スクリーマー.zip")
    file_ja = sub_level_1 / ja_name
    file_ja.write_text("archive compressed tracking info", encoding="utf-8")

    # Level 2 (Deeply Nested Directory)
    sub_level_2 = sub_level_1 / "Deep Level 2"
    sub_level_2.mkdir()
    
    file_lvl_2 = sub_level_2 / "deeply_hidden_file.csv"
    file_lvl_2.write_text("deep records", encoding="utf-8")

    return tmp_path


async def test_spaces_and_non_standard_characters(complex_workspace):
    """Bug 1 & 2 Fix Verification: Verifies spaces and international symbols resolve smoothly."""
    # Test spaces in root files
    raw_stage = await resolve_inputs([str(complex_workspace)], recursive=False)
    filenames = [p.name for p in raw_stage]
    
    assert "my document report final.doc" in filenames
    assert len(raw_stage) == 2


async def test_non_recursive_directory_scan(complex_workspace):
    """Verifies that disabling recursion completely locks tracking to Level 0."""
    raw_stage = await resolve_inputs([str(complex_workspace)], recursive=False)
    
    # Must only find the 2 root files; completely omitting folders deeper down
    assert len(raw_stage) == 2
    for path in raw_stage:
        assert path.parent == complex_workspace


async def test_max_depth_tier_boundaries(complex_workspace):
    """Verifies that max_depth constraints enforce boundary rules accurately."""
    # Scan with max_depth=1 (Should find Level 0 and Level 1 files, but skip Level 2)
    raw_stage_d1 = await resolve_inputs([str(complex_workspace)], recursive=True, max_depth=1)
    filenames_d1 = [p.name for p in raw_stage_d1]
    
    assert "english_invoice_2026.txt" in filenames_d1     # Level 0
    assert "level_1_data.log" in filenames_d1             # Level 1
    assert "ザ・スクリーマー.zip" in filenames_d1          # Level 1
    assert "deeply_hidden_file.csv" not in filenames_d1   # Level 2 (Blocked by max_depth)
    assert len(raw_stage_d1) == 4


async def test_two_pass_language_detection_and_exclusion(complex_workspace):
    """Validates the two-pass engine and isolation rules for language processing maps."""
    raw_stage = await resolve_inputs([str(complex_workspace)], recursive=True)
    
    # Run pass 2 detection targeting Japanese ('ja') exclusion metrics
    registry = await process_language_detection_batch(raw_stage=raw_stage, target_lang="ja")
    
    # Find our specific international tracking paths
    ja_key = [k for k in registry.keys() if "ザ・スクリーマー" in k][0]
    en_key = [k for k in registry.keys() if "english_invoice" in k][0]
    
    # Assert Japanese file matches 'ja' and is flagged for exclusion
    assert registry[ja_key]["detected_lang"] == "ja"
    assert registry[ja_key]["action"] == "EXCLUDE"
    
    # Assert English file matches 'en' and is flagged for active translation processing
    assert registry[en_key]["detected_lang"] == "en"
    assert registry[en_key]["action"] == "TRANSLATE"


async def test_progress_callback_tracking_ticks(complex_workspace):
    """Ensures callback metrics report state increments predictably across processing windows."""
    raw_stage = await resolve_inputs([str(complex_workspace)], recursive=True)
    total_files = len(raw_stage)  # Should total 5 items across all levels
    
    ticks = []
    def progress_tracer(current, total):
        ticks.append((current, total))
        
    await process_language_detection_batch(
        raw_stage=raw_stage, 
        target_lang="es", 
        progress_callback=progress_tracer
    )
    
    assert len(ticks) == total_files
    assert ticks[-1] == (total_files, total_files)  # Final verification tick must balance out

# test_scanner.py
import pytest
from pathlib import Path
from lib.scanner import scan_inputs, resolve_inputs

# Mark all tests in this file as async coroutines
pytestmark = pytest.mark.asyncio

@pytest.fixture
def temp_workspace(tmp_path) -> Path:
    """Creates a temporary isolated directory setup with varying file formats."""
    # Create top level structure
    file_a = tmp_path / "hello_world.txt"
    file_a.write_text("dummy content")
    
    file_b = tmp_path / "already_es.txt"
    file_b.write_text("dummy content")
    
    # Create nested folder structure
    sub_dir = tmp_path / "nested_folder"
    sub_dir.mkdir()
    
    file_c = sub_dir / "deep_file.log"
    file_c.write_text("dummy content")
    
    return tmp_path


async def test_resolve_single_and_comma_separated_inputs(temp_workspace):
    """Verifies scanner handles single files and unpacks comma-separated arguments cleanly."""
    file_1 = str(temp_workspace / "hello_world.txt")
    file_2 = str(temp_workspace / "already_es.txt")
    combined_input = f"{file_1}, {file_2}"
    
    resolved = await resolve_inputs([combined_input], recursive=False)
    
    assert len(resolved) == 2
    assert Path(file_1) in resolved
    assert Path(file_2) in resolved


async def test_non_recursive_directory_scan(temp_workspace):
    """Ensures non-recursive scanning ignores nested subdirectory child content."""
    registry = await scan_inputs([str(temp_workspace)], recursive=False, target_lang="es")
    
    # Should find hello_world.txt and already_es.txt but miss deep_file.log
    assert len(registry) == 2
    
    # Validate structure matches structural spec
    for path, data in registry.items():
        assert "original_filename" in data
        assert data["translation_status"] == "NONE"


async def test_recursive_directory_scan(temp_workspace):
    """Ensures recursive flag correctly traverses nested file trees."""
    registry = await scan_inputs([str(temp_workspace)], recursive=True, target_lang="es")
    
    # Should catch all three files across directories
    assert len(registry) == 3


async def test_language_match_exclusion_rule(temp_workspace):
    """Verifies files already matching target language are mapped directly to EXCLUDE."""
    registry = await scan_inputs([str(temp_workspace)], recursive=True, target_lang="es")
    
    target_path = str(temp_workspace / "already_es.txt")
    
    assert target_path in registry
    assert registry[target_path]["detected_lang"] == "es"
    assert registry[target_path]["action"] == "EXCLUDE"


async def test_progress_callback_ticks(temp_workspace):
    """Validates callback reporting hooks trigger reliably for progress updates."""
    ticks = []
    
    def tracker(current, total):
        ticks.append((current, total))
        
    await scan_inputs([str(temp_workspace)], recursive=True, target_lang="es", progress_callback=tracker)
    
    assert len(ticks) == 3
    assert ticks[-1] == (3, 3)  # Final tick should show full count equilibrium

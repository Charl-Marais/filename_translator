📑 System Technical Specification (Async File TUI Translator)

🗄️ 1. Global Core State Structure

The single source of truth passed between modules. To preserve absolute data integrity, all modules use a file's absolute path as the unique immutable primary key.

```
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

# Master Registry
MasterRegistry = dict[str, FileState]

```

* * * * *

🛠️ 2. Module Specifications

Module 1: Directory Scanner (`scanner.py`)

-   Responsibility: Validate paths, resolve inputs, and crawl targets without holding locks.
-   Key Interface:

    ```
    async def scan_inputs(
        inputs: list[str],
        recursive: bool,
        target_lang: str,
        progress_callback: callable = None
    ) -> MasterRegistry:
        """Sanitises raw inputs (paths/CSVs) and populates the initial Registry."""

    ```

-   Edge Case Actions:
    -   If a file's pre-detected language matches `target_lang`, set `action = "EXCLUDE"` and log `detected_lang`.
    -   Validates path readability/permissions using `os.access()` before starting.

Module 2: Translation Core (`translator.py`)

-   Responsibility: Execute bulk asynchronous HTTP requests, managing a private sub-hash task buffer.
-   Key Interface:

    ```
    class AsyncTranslationEngine:
        def __init__(self, target_lang: str, batch_size: int = 100): ...

        async def process_batch(self, sub_hash: dict[str, FileState]) -> dict[str, FileState]:
            """Accepts a sub-hash slice, hits bulk API, updates text/statuses, returns results."""

    ```

-   Isolation Guarantee: This module never touches the Master Registry directly. It receives an isolated slice snapshot and returns an updated copy.

Module 3: Renamer Worker (`renamer.py`)

-   Responsibility: Safe disk mutations (I/O) avoiding path collisions.
-   Key Interface:

    ```
    class DiskRenamerEngine:
        async def execute_rename(self, sub_hash: dict[str, FileState]) -> dict[str, FileState]:
            """Executes physical os.rename operations wrapped in absolute exception handling."""

    ```

-   Safety Interlocks:
    -   Checks if the target filename already exists in the destination folder before execution.
    -   If a target collision or permission failure occurs, sets `rename_status = "FAILED"` and populates `error_message`.

Module 4: Automatic Orchestrator (`orchestrator.py`)

-   Responsibility: The heartbeat thread of Auto Mode. Manages state synchronization, time-window accumulation buffers, and auto-retries.
-   Key Interface:

    ```
    class PipelineOrchestrator:
        def __init__(self, master_registry: MasterRegistry, max_retries: int = 3): ...

        async def start_auto_loop(self):
            """Continuous loop pulling, dispatching, and reconciling sub-hash states."""

    ```

-   The Orchestration Cycle Protocol:
    1.  Pull: Scans `MasterRegistry` for `action == "TRANSLATE"` and `translation_status == "NONE"`.
    2.  Buffer: Packs extracted nodes into a sub-hash chunk until `batch_size` is hit or a `linger_timer` expires.
    3.  Dispatch: Sets Master nodes to `PROCESSING_TX`, passes sub-hash to `AsyncTranslationEngine`.
    4.  Reconcile: Syncs returned sub-hash data directly back to Master. Sets nodes to `action = "RENAME"`.
    5.  Retry Engine: If an execution fails, increments `retry_count`. If `retry_count < max_retries`, resets state for a retry window. If exceeded, flags as terminal error.

Module 5 & 6: Interface Layers (`cli.py` & `tui.py`)

-   Responsibility: Presentation and lifecycle triggers.
-   CLI Mode: Simple, fast scripts passing data directly through a single programmatic automation pass.
-   TUI Mode (Textual): A reactive UI layer driven entirely by `asyncio`. Binds widgets directly to the `MasterRegistry` dictionary, displaying updates using safe scheduled UI ticks.

* * * * *

🧪 3. Incremental Test Driven Approach

To make this seamless, we should write and test these pieces in an isolated, ascending sequence.

Phase 1: Core Drivers (No UI)

1.  Test 1 (Scanner): Verify mock CSV strings, mixed relative paths, and recursive subdirectory configurations return correctly sized `MasterRegistry` dictionaries.
2.  Test 2 (Translator): Mock network boundaries using `pytest-asyncio` and `unittest.mock`. Ensure that sending a dictionary chunk yields matching keys back with clean statuses.
3.  Test 3 (Renamer): Create a temporary directory structure (`tmp_path`), populate mock text files, run the engine, and assert file paths physically changed names on disk.

Phase 2: System Control & UI

1.  Test 4 (Orchestrator Loop): Wire up the mock components into the Orchestrator engine. Feed it a broken state or simulate random network drops to verify items accurately scale up their retry increments up to the maximum limit.
2.  Test 5 (Interface Assembly): Wrap our functional state engines behind Textual components and CLI argument parsers.

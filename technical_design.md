🗄️ 1. Core State Architecture (The Master Hash Table)

To make this pipeline dynamic, non-blocking, and capable of rollbacks or updates, we need a single source of truth. The global hash table will use the absolute file path as the unique key.

```
{
    "/absolute/path/to/file1.txt": {
        "original_filename": "file1.txt",
        "base_name": "file1",
        "extension": ".txt",
        "current_dir": "/absolute/path/to",
        "detected_lang": "en",
        "target_lang": "es",
        "action": "PENDING",          # PENDING, TRANSLATE, EXCLUDE, RENAME, COMPLETED
        "translation_status": "NONE",  # NONE, PROCESSING, SUCCESS, FAILED
        "translated_text": "",
        "rename_status": "NONE",       # NONE, PROCESSING, SUCCESS, FAILED
        "new_filename": "",
        "error_message": "",
        "retry_count": 0
    }
}

```

* * * * *

🎛️ 2. Step-by-Step Program Flow Matrix

Here is how the pipeline operates, comparing the manual gates of Interactive Mode against the reactive behaviors of Auto Mode:

| Stage | 🛠️ Interactive Mode | ⚡ Auto Mode |
| 1\. Collection | Scans inputs \(\rightarrow \) Populates Hash \(\rightarrow \) Pauses for User Review (add/remove items). | Scans inputs \(\rightarrow \) Streams files immediately to the Translation pipeline. |
| 2\. Translation | Translates approved batch \(\rightarrow \) Updates Hash \(\rightarrow \) Pauses for User Review (exclude/re-translate). | Evaluates buffer \(\rightarrow \) Translates continuously \(\rightarrow \) Streams directly to Renamer. |
| 3\. Execution | Renames files \(\rightarrow \) Displays final stats \(\rightarrow \) Pauses for User Loop (retry errors, exit). | Processes renames instantly \(\rightarrow \) Triggers auto-retries (up to max configured) on failure \(\rightarrow \) Exits cleanly. |

* * * * *

📐 3. Feature Set & Functional Requirements

A. command line inputs

The application should accept the following command line inputs:

- directory path or files to scan
- mode - auto or interactive
- target language
- set max retries for failed translations and renames. default is 0.
- log level - 0 - error, 1 - warning, 2 - info, 3 - debug
- skip tui confirmation - if this is set then the tui will not be shown and the application will proceed with the settings passed in command line or the defaults if no settings were passed. This is useful for using the application in a headless environment or in conjuction with scripts to automate the renaming of files. 

B. TUI Terminal Interface

We will use the textual library to create the TUI Terminal Interface. When first started up it will allow the user to confirm the setting passed in command line or if no settings were passed then just to proceed with setting them if not happy with the defaults.

🎛️ Mapping the TUI Screen Layout

Because your pipeline has precise steps, the TUI screen can change context smoothly based on your architecture phases:
+──────────────────────────────────────────────────────────────────────────────+

|  🔄 ASYNC BATCH FILE TRANSLATOR [Auto Mode]                    [Files: 1042] |
+──────────────────────────────────────────────────────────────────────────────+

|  🔍 COLLECTION PATH: ./my_large_folder/                                     |
|  [████████████████████████████████████████████] 100% (Scanned: 1042 / Found: 89) |
+──────────────────────────────────────────────────────────────────────────────+

|  Active Pipelines:                                                           |
|  [Network Buffer] Active Batch: 42/100  │ [Disk I/O Worker] Idle             |
+──────────────────────────────────────────────────────────────────────────────+

|  FILE RECONCILIATION REGISTRY:                                               |
|  Path                    │ Target Lang │ TX Status   │ IO Status  │ Retries  |
|  ────────────────────────┼─────────────┼─────────────┼────────────┼──────────│

|  /books/ch1_intro.txt    │ es          │ ✅ SUCCESS  │ ⏳ PENDING │ 0 / 3    |
|  /books/ch2_final.txt    │ es          │ 🔄 ACTIVE   │ ───        │ 0 / 3    |
|  /books/notes_es.txt     │ es          │ ⏩ SKIPPED  │ ───        │ 0 / 3    |
|  /books/summary_bad.txt  │ es          │ ❌ FAILED   │ ───        │ 1 / 3    |
+──────────────────────────────────────────────────────────────────────────────+

|  [F2] Toggle View  │  [F5] Pause Pipeline  │  [F9] Trigger Manual Retry     |
+──────────────────────────────────────────────────────────────────────────────+

* * * * *

🎨 4. Modes of operation

There are two modes in which the application can operate. Interactive mode is where user can review the items on some or all of the stages, for example user can review the items after translation and then decide to rename or not. Auto mode is where the application will run with no user interaction except to provide user feedback in the form of a running total of items processed and a percentage counter.  

### Interactive mode

In interactive mode the application will process the stages sequentially. It will not proceed to the next stage until the user has approved the results of the current stage. This is done through the use of sub-hashes which are copies of the main hash table that are used to manage the state of each stage.

🔄 The Main Hash Orchestrator

Your decoupled orchestrator pattern acts as the "Traffic Controller" using an immutable data-passing cycle:
                  ┌──────────────────────────────┐
                  │       MAIN HASH TABLE        │
                  │ (Single Source of Truth / UI)│
                  └──────────────┬───────────────┘
                                 │ ▲
     1. Dispatches Pending Units │ │ 4. Syncs Sub-States & Results
                                 ▼ │
        ┌────────────────────────┴─┴────────────────────────┐
        │               ORCHESTRATOR ENGINE                 │
        └──────────────┬──────────────────────┬─────────────┘
                       │                      │
                       ▼                      ▼
  ┌──────────────────────────────┐     ┌──────────────────────────────┐
  │    TRANSLATION SUB-HASH      │     │      RENAMING SUB-HASH       │
  │ (Isolated API Worker Buffer) │     │ (Isolated Disk I/O Worker)   │
  └──────────────────────────────┘     └──────────────────────────────┘

The Lifecycle Sync Protocol:

1. Extraction: The Orchestrator constantly polls the Main Hash. It pulls out items where action == "TRANSLATE" and translation_status == "NONE", changing their main status to "PROCESSING_TX".
2. Isolation: It moves these cloned structures into the Translation Sub-Hash. The Translation Loop only watches this sub-hash.
3. Execution & Return: The Translation Engine processes its sub-hash, tags them as SUCCESS or FAILED, and records errors.
4. Reconciliation: The Orchestrator pulls the results out of the sub-hash, matches them back to the Main Hash via their absolute paths, clears the sub-hash, and changes the main state to "PENDING_RENAME" (or increments the retry engine if it failed).

### Auto Mode

In auto mode the application will parallise the stages to complete the work more quickly. However in order to prevent clashes there will be an orchestrator pattern to manage the passing of data between the stages. This is done through the use of sub-hashes which are copies of the main hash table that are used to manage the state of each stage.

🔄 The Main Hash Orchestrator

Your decoupled orchestrator pattern acts as the "Traffic Controller" using an immutable data-passing cycle:
                  ┌──────────────────────────────┐
                  │       MAIN HASH TABLE        │
                  │ (Single Source of Truth / UI)│
                  └──────────────┬───────────────┘
                                 │ ▲
     1. Dispatches Pending Units │ │ 4. Syncs Sub-States & Results
                                 ▼ │
        ┌────────────────────────┴─┴────────────────────────┐
        │               ORCHESTRATOR ENGINE                 │
        └──────────────┬──────────────────────┬─────────────┘
                       │                      │
                       ▼                      ▼
  ┌──────────────────────────────┐     ┌──────────────────────────────┐
  │    TRANSLATION SUB-HASH      │     │      RENAMING SUB-HASH       │
  │ (Isolated API Worker Buffer) │     │ (Isolated Disk I/O Worker)   │
  └──────────────────────────────┘     └──────────────────────────────┘

The Lifecycle Sync Protocol:

1. Extraction: The Orchestrator constantly polls the Main Hash. It pulls out items where action == "TRANSLATE" and translation_status == "NONE", changing their main status to "PROCESSING_TX".
2. Isolation: It moves these cloned structures into the Translation Sub-Hash. The Translation Loop only watches this sub-hash.
3. Execution & Return: The Translation Engine processes its sub-hash, tags them as SUCCESS or FAILED, and records errors.
4. Reconciliation: The Orchestrator pulls the results out of the sub-hash, matches them back to the Main Hash via their absolute paths, clears the sub-hash, and changes the main state to "PENDING_RENAME" (or increments the retry engine if it failed).


1. 🎛️ The Orchestrator
The Orchestrator is the brain of the operation. It is a long-running process (daemon)
that is responsible for managing the entire pipeline. It is the only process that
has access to the main hash table.

The Orchestrator is responsible for the following:

-   Scanning the input directories for files to process
-   Creating new items in the hash table for each file
-   Translating the filenames in the hash table
-   Renaming the files in the hash table
-   Managing the retry logic for failed translations or renames
-   Managing the accumulation strategy for auto mode

2. 🔄 The Translation Sub-Hash
The Translation Sub-Hash is a temporary hash table that is used to manage the
translation stage of the pipeline. It is a copy of the main hash table that is used
to manage the translation stage of the pipeline.

The Translation Sub-Hash is responsible for the following:

-   Managing the translation stage of the pipeline
-   Translating the filenames in the hash table
-   Managing the retry logic for failed translations
-   Managing the accumulation strategy for auto mode

3. 📂 The Rename Sub-Hash
The Rename Sub-Hash is a temporary hash table that is used to manage the rename
stage of the pipeline. It is a copy of the main hash table that is used to manage
the rename stage of the pipeline.

The Rename Sub-Hash is responsible for the following:

-   Managing the rename stage of the pipeline
-   Renaming the files in the hash table
-   Managing the retry logic for failed renames
-   Managing the accumulation strategy for auto mode

B. The Accumulation Strategy (Auto Mode Edge Cases)

What if Auto Mode receives only 1 file, or the total count is less than the ideal batch size when translating?
Should we wait or just process the small batchsize? 

I think in this case we should sleep 1 second between each call and process what ever we have to process unless the quantaty is reached for the batch. In this case we will just process the work in multiple batches. The primary purpose with this approach is prevent rate-limiting and so even if we process a single file we will still sleep 1 second between the call and the next call as well as thime taken for translation to give the other processes time to accumulate more work for translation. So effeciancy is still maintained. 

1.  Capacity Valve: The buffer releases items to the translator the instant the number of accumulated files reaches `BATCH_SIZE` (e.g., 50 files).
2.  Timeout Valve (The Linger Timer): If the buffer contains *any* files but hasn't reached capacity, a brief countdown (e.g., 500ms to 1.5s) runs. If no new files arrive before the timer runs out, it flushes the remaining files immediately.
3.  *Exception:* If the initial scan calculates that the *total* file pool is smaller than `BATCH_SIZE`, the linger timer is bypassed entirely, and translation triggers instantly upon scan completion.

C. Failure & Retry Sub-Engine

-   Configurable Threshold: Default to `3` retries.
-   Translation Failures: Caught at the batch level. Failed strings degrade their item statuses to `FAILED` and log the error message. In Auto Mode, these are automatically re-queued up to 3 times. In Interactive Mode, they populate a "Retry List" for the user.
-   Rename Failures: Usually caused by permission errors, locked files, or duplicate target names. Handled safely via try/except blocks to ensure a single file crash never bring down a 1000-file pipeline.

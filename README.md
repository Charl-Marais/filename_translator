
### Project Description

This is a command-line tool that translates filenames from one language to another in batches. It uses the `googletrans` to translate the filenames and the `argparse` library to parse the command-line arguments.

It can be run in different modes:
- dry-run: only print the translated filenames
- interactive mode with tui
- automatic mode with tui printout
- automatic mode headless only writes to logs

### Run tests locally

To run these tests locally, make sure you have `pytest` and `pytest-asyncio` installed:


1. test directory scanner

```bash
pip install pytest pytest-asyncio
pytest test_scanner.py
```

2. test translator
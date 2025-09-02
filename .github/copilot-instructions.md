# FastGet
FastGet is a Python CLI application that downloads files using multiple threads for faster download speeds. It supports HTTP range requests to download file parts in parallel and merges them together.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively
- Bootstrap, setup, and validate the repository:
  - `python3 --version` -- verify Python 3.12+ is available
  - `python3 -m pip install --upgrade pip`
  - `python3 -m pip install -r requirements.txt` -- installs requests and rich libraries
  - `python3 -m py_compile fastget.py` -- validate Python syntax
- Build standalone executable:
  - `python3 -m pip install pyinstaller ordered-set zstandard pefile` -- install build dependencies
  - `time pyinstaller --onefile --distpath dist --name fastget fastget.py` -- NEVER CANCEL: takes 15-25 seconds. Set timeout to 60+ seconds.
- Run the application:
  - Python script: `python3 fastget.py`
  - Built executable: `./dist/fastget`
  - Both versions prompt for: URL, output filename (optional), number of threads (default 8)

## Validation
- ALWAYS test functionality manually after making changes using the validation scenarios below.
- The application works correctly but network restrictions in CI environments may prevent downloads.
- ALWAYS run through at least one complete download scenario after making changes when network access is available.
- ALWAYS run `python3 -m py_compile fastget.py` before committing to validate Python syntax.
- Build validation: `time pyinstaller --onefile --distpath dist --name fastget fastget.py` should complete in 15-25 seconds.

## Manual Validation Scenarios
When network access is available, test these scenarios:

### Basic Download Test
```bash
python3 fastget.py
# When prompted:
# URL: https://speed.hetzner.de/1KB.bin
# Save as: test.bin (or press Enter)
# Threads: 4
# Expected: Downloads 1KB file quickly with progress bar
```

### Multi-threading Test
```bash
python3 fastget.py
# When prompted:
# URL: https://speed.hetzner.de/10MB.bin
# Save as: large_test.bin
# Threads: 8
# Expected: Downloads 10MB file using multiple threads with progress
```

### Single Thread Fallback Test
```bash
python3 fastget.py
# When prompted:
# URL: https://httpbin.org/bytes/1024
# Save as: single_thread.bin
# Threads: 4
# Expected: Detects no range support, falls back to single thread
```

### Executable Test
```bash
./dist/fastget
# Run same tests as above using the built executable
# Expected: Same behavior as Python script
```

### Validation Criteria
✓ Application starts without errors
✓ Prompts for URL, filename, and threads
✓ Shows rich progress bar during download
✓ Creates output file with correct size
✓ Handles range/non-range servers correctly
✓ Multi-threading works when supported
✓ Single-thread fallback works when needed

## Build Process Details
- Build command: `pyinstaller --onefile --distpath dist --name fastget fastget.py`
- NEVER CANCEL: Build takes 15-25 seconds. ALWAYS set timeout to 60+ seconds minimum.
- Output: Single executable file in `dist/fastget` (Linux/macOS) or `dist/fastget.exe` (Windows)
- Size: Approximately 14MB for Linux build
- Dependencies embedded: Python runtime, requests, rich, and all required libraries

## Common Tasks
The following are outputs from frequently run commands. Reference them instead of viewing, searching, or running bash commands to save time.

### Repository Structure
```
ls -la
.
..
.git/
.github/
  workflows/
    fastget-build.yml    # CI build workflow
LICENSE                  # MIT License
README.md               # Basic project description
fastget.py              # Main Python application (106 lines)
requirements.txt        # Python dependencies (requests, rich)
```

### Dependencies
```
cat requirements.txt
requests
rich
```

### Main Application Structure
```
fastget.py contains:
- VERSION = "2.0"
- Interactive prompts for URL, output file, threads
- get_file_size() - checks Content-Length and Accept-Ranges headers
- download_range() - downloads file chunk with Range header
- merge_files() - combines downloaded parts into final file
- main() - orchestrates the download process
```

### Build Dependencies
```
pip install pyinstaller ordered-set zstandard pefile
```

## CI/CD Information
- GitHub Actions workflow: `.github/workflows/fastget-build.yml`
- Builds on release for multiple platforms: Windows, macOS, Linux (both x64 and ARM64)
- Uses Python 3.12
- Build artifacts uploaded as GitHub release assets
- Build time in CI: varies by platform, allow 5-10 minutes for full matrix

## Known Limitations
- No unit tests exist in the repository
- No linting tools configured (flake8, pylint not available)
- Network restrictions in some CI environments prevent download testing
- Application is interactive only - no command-line argument support
- No --help option available

## Code Quality
- Always run `python3 -m py_compile fastget.py` to validate syntax before committing
- The code follows basic Python conventions
- Uses rich library for progress display and user prompts
- Implements proper error handling for network requests
- Thread-safe file writing with part files merged at the end

## Troubleshooting
- Import errors: Ensure `pip install -r requirements.txt` completed successfully
- Build errors: Verify all build dependencies are installed
- Network errors during testing: Expected in restricted environments, test manually when possible
- Permission errors: Ensure executable permissions on `dist/fastget` after build
import os
import math
import requests
from threading import Thread, Lock
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime, timezone
from nercone_modern.logging import ModernLogging
from nercone_modern.progressbar import ModernProgressBar

console = Console()
logger = ModernLogging(process_name="FastGet")

VERSION = "2.0"
URL = Prompt.ask("URL")
OUTPUT_FILE = Prompt.ask("Save as", default=os.path.basename(URL))
THREADS = int(Prompt.ask("Threads", default=8))

DOWNLOAD_CHUNK = 1024 * 128   # 128KB
MERGE_CHUNK    = 1024 * 256   # 256KB

progress_lock = Lock()

def get_file_size(url):
    response = requests.head(url, allow_redirects=True)
    if response.status_code == 200:
        file_size = int(response.headers.get('Content-Length', 0))
        accept_ranges = response.headers.get('Accept-Ranges', 'none')
        reject_fastget = response.headers.get('RejectFastGet', '').lower() in ['true', '1', 'yes']
        return file_size, accept_ranges.lower() == 'bytes', reject_fastget
    else:
        raise Exception(f"Failed to retrieve file info. Status code: {response.status_code}")

def download_range(url, start, end, part_num, progress_bar, headers=None):
    headers = headers or {}
    headers.update({'User-Agent': f'FastGet/{VERSION} (Downloading with {THREADS} Thread(s), {part_num} Part(s), https://github.com/DiamondGotCat/FastGet/)'})
    headers.update({'Range': f'bytes={start}-{end}'})
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Error downloading part {part_num}: {e}[/red]")
        return

    part_path = f"{OUTPUT_FILE}.part{part_num}"
    with open(part_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
            if not chunk:
                continue
            f.write(chunk)
            with progress_lock:
                progress_bar.update()

def merge_files(parts, output_file):
    total_size = 0
    for part in parts:
        try:
            total_size += os.path.getsize(part)
        except OSError:
            pass

    total_steps = max(1, math.ceil(total_size / MERGE_CHUNK))
    merge_bar = nm.modernProgressBar(total=total_steps, process_name="Marge", process_color=33, spinner_mode=False)
    merge_bar.start()

    try:
        with open(output_file, 'wb') as outfile:
            for part in parts:
                if not os.path.exists(part):
                    continue
                with open(part, 'rb') as infile:
                    while True:
                        chunk = infile.read(MERGE_CHUNK)
                        if not chunk:
                            break
                        outfile.write(chunk)
                        merge_bar.update()
    finally:
        merge_bar.finish()

    for part in parts:
        try:
            os.remove(part)
        except OSError:
            pass

def main():
    global THREADS
    try:
        file_size, is_resumable, is_fastget_rejected = get_file_size(URL)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if is_fastget_rejected:
        console.print("[yellow]Server has rejected FastGet parallel downloads. Downloading in single thread...[/yellow]")
        THREADS = 1
    elif not is_resumable:
        console.print("[yellow]Server has not supported multiple threads. Downloading in single thread...[/yellow]")
        THREADS = 1

    part_size = file_size // THREADS if THREADS > 0 else file_size
    threads = []
    parts = [f"{OUTPUT_FILE}.part{i}" for i in range(THREADS)]

    total_download_steps = max(1, math.ceil(file_size / DOWNLOAD_CHUNK))
    download_bar = ModernProgressBar(total=total_download_steps, process_name="Download", spinner_mode=False)
    download_bar.start()
    start_time = datetime.now(timezone.utc)
    for i in range(THREADS):
        start = part_size * i
        end = file_size - 1 if i == THREADS - 1 else start + part_size - 1
        thread = Thread(target=download_range, args=(URL, start, end, i, download_bar))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    end_time = datetime.now(timezone.utc)
    delta = end_time - start_time
    duration_ms = delta.days*24*3600*1000 + delta.seconds*1000 + delta.microseconds//1000
    download_bar.finish()

    try:
        merge_files(parts, OUTPUT_FILE)
        console.print(f"[green]Download completed in {duration_ms}ms: {OUTPUT_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Error merging files: {e}[/red]")

if __name__ == "__main__":
    main()

import os
import requests
from threading import Thread
from rich.progress import Progress
from rich.console import Console
from rich.prompt import Prompt

console = Console()

VERSION = "2.0"
URL = Prompt.ask("URL")
OUTPUT_FILE = Prompt.ask("Save as", default=os.path.basename(URL))
THREADS = int(Prompt.ask("Threads", default=8))

def get_file_size(url):
    response = requests.head(url, allow_redirects=True)
    if response.status_code == 200:
        file_size = int(response.headers.get('Content-Length', 0))
        accept_ranges = response.headers.get('Accept-Ranges', 'none')
        reject_fastget = response.headers.get('RejectFastGet', '').lower() in ['true', '1', 'yes']
        return file_size, accept_ranges.lower() == 'bytes', reject_fastget
    else:
        raise Exception(f"Failed to retrieve file info. Status code: {response.status_code}")

def download_range(url, start, end, part_num, progress, task_id, headers=None):
    headers = headers or {}
    headers.update({'User-Agent': f'FastGet/{VERSION} (Downloading with {THREADS} Thread(s), {part_num} Part(s), https://github.com/DiamondGotCat/FastGet/)'})
    headers.update({'Range': f'bytes={start}-{end}'})
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Error downloading part {part_num}: {e}[/red]")
        return

    with open(f"{OUTPUT_FILE}.part{part_num}", 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 128):
            if chunk:
                f.write(chunk)
                progress.update(task_id, advance=len(chunk))

def merge_files(parts, output_file):
    total_size = 0
    for part in parts:
        try:
            total_size += os.path.getsize(part)
        except OSError:
            pass

    with Progress() as progress:
        merge_task = progress.add_task("Merging", total=total_size)

        with open(output_file, 'wb') as outfile:
            for part in parts:
                with open(part, 'rb') as infile:
                    # チャンクで読み書きしつつ進捗更新
                    while True:
                        chunk = infile.read(1024 * 256)
                        if not chunk:
                            break
                        outfile.write(chunk)
                        progress.update(merge_task, advance=len(chunk))

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
        console.print("Server has rejected FastGet parallel downloads. Downloading in single thread...")
        THREADS = 1
    elif not is_resumable:
        console.print("Server has not supported multiple threads. Downloading in single thread...")
        THREADS = 1

    part_size = file_size // THREADS if THREADS > 0 else file_size
    threads = []
    parts = [f"{OUTPUT_FILE}.part{i}" for i in range(THREADS)]

    with Progress() as progress:
        task_id = progress.add_task("Downloading", total=file_size)

        for i in range(THREADS):
            start = part_size * i
            end = file_size - 1 if i == THREADS - 1 else start + part_size - 1
            thread = Thread(target=download_range, args=(URL, start, end, i, progress, task_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    try:
        merge_files(parts, OUTPUT_FILE)
        console.print(f"[green]Download completed: {OUTPUT_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Error merging files: {e}[/red]")

if __name__ == "__main__":
    main()

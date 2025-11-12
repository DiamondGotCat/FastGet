import os, math, requests, argparse
from threading import Thread, Lock
from urllib.parse import urlparse, unquote
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime, timezone
from nercone_modern.progressbar import ModernProgressBar

console = Console()

VERSION = "4.1"
CHUNK = 1024 * 128 # 128KB

progress_lock = Lock()

def get_file_name(url):
    return unquote(os.path.basename(urlparse(url).path))

def get_file_size(url):
    response = requests.head(url, allow_redirects=True)
    if response.status_code == 200:
        file_size = int(response.headers.get('Content-Length', 0))
        accept_ranges = response.headers.get('Accept-Ranges', 'none')
        reject_fastget = response.headers.get('RejectFastGet', '').strip().lower() in ['1', 'y', 'yes', 'true', 'enabled']
        return file_size, accept_ranges.lower() == 'bytes', reject_fastget
    else:
        raise Exception(f"Failed to retrieve file info. Status code: {response.status_code}")

def download_range(url, start, end, part_num, output, threads, all_bar: ModernProgressBar, thread_bar: ModernProgressBar, headers=None):
    headers = headers or {}
    headers.update({'User-Agent': f'FastGet/{VERSION} (Downloading with {threads} Thread(s), {part_num} Part(s), https://github.com/DiamondGotCat/FastGet/)'})
    headers.update({'Range': f'bytes={start}-{end}'})
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        thread_bar.setMessage(f"RequestException: {e}")
        return

    part_path = f"{output}.part{part_num}"
    with open(part_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK):
            if not chunk:
                continue
            f.write(chunk)
            with progress_lock:
                thread_bar.update()
                all_bar.update()

def merge_files(parts, output_file):
    total_size = 0
    for part in parts:
        try:
            total_size += os.path.getsize(part)
        except OSError:
            pass

    total_steps = max(1, math.ceil(total_size / CHUNK))
    merge_bar = ModernProgressBar(total=total_steps, process_name="Marge", spinner_mode=False)
    merge_bar.start()

    try:
        with open(output_file, 'wb') as outfile:
            for part in parts:
                if not os.path.exists(part):
                    continue
                with open(part, 'rb') as infile:
                    while True:
                        chunk = infile.read(CHUNK)
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
    parser = argparse.ArgumentParser(prog='FastGet', description='High-speed File Downloading Tool')
    parser.add_argument('url')
    parser.add_argument('-o', '--output', default=None)
    parser.add_argument('-t', '--threads', default=4, type=int)
    args = parser.parse_args()

    if args.output is None:
        args.output = get_file_name(args.url)

    try:
        file_size, is_resumable, is_fastget_rejected = get_file_size(args.url)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    threads = args.threads
    if is_fastget_rejected:
        console.print("[yellow]Server has rejected FastGet parallel downloads. Downloading in single thread...[/yellow]")
        threads = 1
    elif not is_resumable:
        console.print("[yellow]Server has not supported multiple threads. Downloading in single thread...[/yellow]")
        threads = 1

    part_size = file_size // threads if threads > 0 else file_size
    parts = [f"{args.output}.part{i}" for i in range(threads)]

    total_download_steps = max(1, math.ceil(file_size / CHUNK))
    download_bar_all = ModernProgressBar(total=total_download_steps, process_name="DL All", spinner_mode=False)

    thread_bars = []
    for i in range(threads):
        start = part_size * i
        end = file_size - 1 if i == threads - 1 else start + part_size - 1
        part_bytes = max(0, end - start + 1)
        part_steps = max(1, math.ceil(part_bytes / CHUNK))
        bar = ModernProgressBar(total=part_steps, process_name=f"DL #{i + 1}", spinner_mode=False)
        thread_bars.append(bar)

    download_bar_all.start()
    for bar in thread_bars:
        bar.start()

    start_time = datetime.now(timezone.utc)
    thread_objs = []
    for i in range(threads):
        start = part_size * i
        end = file_size - 1 if i == threads - 1 else start + part_size - 1
        thread = Thread(
            target=download_range,
            args=(args.url, start, end, i, args.output, threads, download_bar_all, thread_bars[i])
        )
        thread_objs.append(thread)
        thread.start()

    for thread in thread_objs:
        thread.join()
    end_time = datetime.now(timezone.utc)
    delta = end_time - start_time
    duration_ms = delta.days*24*3600*1000 + delta.seconds*1000 + delta.microseconds//1000

    download_bar_all.finish()
    for bar in thread_bars:
        bar.finish()

    try:
        merge_files(parts, args.output)
        console.print(f"[green]Download completed in {duration_ms}ms: {args.output}[/green]")
    except Exception as e:
        console.print(f"[red]Error merging files: {e}[/red]")

if __name__ == "__main__":
    main()

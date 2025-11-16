import os, math, requests, argparse
from importlib.metadata import version
from typing import Union, Literal
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from threading import Thread, Lock, Event
from urllib.parse import urlparse, unquote
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime, timezone
from nercone_modern.progressbar import ModernProgressBar

console = Console()

VERSION = version("nercone-fastget")
CHUNK = 1024 * 128 # 128KB

progress_lock = Lock()
stop_event = Event()

def get_file_name(url):
    return unquote(os.path.basename(urlparse(url).path))

def get_file_size(url):
    response = requests.head(url, allow_redirects=True)
    if response.status_code in [200, 302]:
        file_size = int(response.headers.get('Content-Length', 0))
        accept_ranges = response.headers.get('Accept-Ranges', 'none')
        reject_fastget = response.headers.get('RejectFastGet', '').strip().lower() in ['1', 'y', 'yes', 'true', 'enabled']
        return file_size, accept_ranges.lower() == 'bytes', reject_fastget
    else:
        raise Exception(f"Failed to retrieve file info. Status code: {response.status_code}")

def format_filesize(num_bytes: Union[int, float], *, decimals: int = 2, rounding: Literal["half_up", "floor"] = "half_up", strip_trailing_zeros: bool = False) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
    try:
        n = int(num_bytes)
    except Exception as e:
        raise TypeError("num_bytes must be a number that can be converted to an integer") from e
    sign = "-" if n < 0 else ""
    b = abs(n)
    if b < 1000:
        return f"{sign}{b} B ({sign}{b:,} B)"
    value = Decimal(b)
    idx = 0
    thousand = Decimal(1000)
    while value >= thousand and idx < len(units) - 1:
        value /= thousand
        idx += 1
    q = Decimal(f"1e-{decimals}") if decimals > 0 else Decimal(1)
    mode = ROUND_HALF_UP if rounding == "half_up" else ROUND_DOWN
    rounded = value.quantize(q, rounding=mode)
    if strip_trailing_zeros and decimals > 0:
        short = f"{rounded.normalize()}"
        if "E" in short or "e" in short:
            short = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    else:
        short = f"{rounded:.{decimals}f}" if decimals > 0 else f"{int(rounded)}"
    return f"{sign}{short}{units[idx]} ({sign}{b:,} B)"

def download_range(url, start, end, part_num, output, threads, all_bar: ModernProgressBar, thread_bar: ModernProgressBar, headers=None, stop: Event = None):
    headers = headers or {}
    headers.update({'User-Agent': f'FastGet/{VERSION} (Downloading with {threads} Thread(s), {part_num} Part(s), https://github.com/DiamondGotCat/FastGet/)'})
    headers.update({'Range': f'bytes={start}-{end}'})
    if stop and stop.is_set():
        return
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        thread_bar.setMessage(f"RequestException: {e}")
        return

    part_path = f"{output}.part{part_num}"
    try:
        with open(part_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK):
                if stop and stop.is_set():
                    break
                if not chunk:
                    continue
                f.write(chunk)
                with progress_lock:
                    thread_bar.update()
                    all_bar.update()
    finally:
        try:
            response.close()
        except Exception:
            pass

def merge_files(parts, output_file):
    total_size = 0
    for part in parts:
        try:
            total_size += os.path.getsize(part)
        except OSError:
            pass

    total_steps = max(1, math.ceil(total_size / CHUNK))
    merge_bar = ModernProgressBar(total=total_steps, process_name="Marge", spinner_mode=False, box_left="(", box_right=")", show_bar=False)
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

    console.print(f"[blue][bold]Total file size:[/bold] [not bold]{format_filesize(file_size)}[/not bold][/blue]")

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
    download_bar_all = ModernProgressBar(total=total_download_steps, process_name="DL All", spinner_mode=False, box_left="(", box_right=")", show_bar=False)

    thread_bars = []
    for i in range(threads):
        start = part_size * i
        end = file_size - 1 if i == threads - 1 else start + part_size - 1
        part_bytes = max(0, end - start + 1)
        part_steps = max(1, math.ceil(part_bytes / CHUNK))
        bar = ModernProgressBar(total=part_steps, process_name=f"DL #{i + 1}", spinner_mode=False, box_left="(", box_right=")", show_bar=False)
        thread_bars.append(bar)

    download_bar_all.start()
    for bar in thread_bars:
        bar.start()

    start_time = datetime.now(timezone.utc)
    thread_objs = []
    try:
        for i in range(threads):
            start = part_size * i
            end = file_size - 1 if i == threads - 1 else start + part_size - 1
            thread = Thread(
                target=download_range,
                args=(args.url, start, end, i, args.output, threads, download_bar_all, thread_bars[i], None, stop_event)
            )
            thread_objs.append(thread)
            thread.start()

        for thread in thread_objs:
            thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        console.print("[red]Interrupted. Stopping threads and cleaning up... [/red]", end="")
        for thread in thread_objs:
            try:
                thread.join()
            except Exception:
                pass
        for part in parts:
            try:
                if os.path.exists(part):
                    os.remove(part)
            except Exception:
                pass
        try:
            if os.path.exists(args.output):
                os.remove(args.output)
        except Exception:
            pass
        console.print("[red]Done.[/red]")
        return

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

import os
import requests
from threading import Thread
from rich.progress import Progress
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# ダウンロードするファイルのURL
URL = Prompt.ask("URL")

# 保存先ファイル名
OUTPUT_FILE = Prompt.ask("Save as", default=os.path.basename(URL))

# スレッド数（同時接続数）
THREADS = int(Prompt.ask("Threads", default=8))

def get_file_size(url):
    """
    ファイルのサイズを取得する関数
    """
    response = requests.head(url, allow_redirects=True)
    if response.status_code == 200:
        file_size = int(response.headers.get('Content-Length', 0))
        accept_ranges = response.headers.get('Accept-Ranges', 'none')
        return file_size, accept_ranges.lower() == 'bytes'
    else:
        raise Exception(f"Failed to retrieve file info. Status code: {response.status_code}")

def download_range(url, start, end, part_num, progress, task_id, headers=None):
    """
    指定された範囲をダウンロードする関数
    """
    headers = headers or {}
    headers.update({'Range': f'bytes={start}-{end}'})
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Error downloading part {part_num}: {e}[/red]")
        return

    with open(f"{OUTPUT_FILE}.part{part_num}", 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                progress.update(task_id, advance=len(chunk))

def merge_files(parts, output_file):
    """
    ダウンロードしたパーツを結合する関数
    """
    with open(output_file, 'wb') as outfile:
        for part in parts:
            with open(part, 'rb') as infile:
                outfile.write(infile.read())
            os.remove(part)

def main():
    global THREADS
    try:
        file_size, is_resumable = get_file_size(URL)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not is_resumable:
        console.print("Server has not supported multiple threads. Downloading in single thread...")
        THREADS = 1

    part_size = file_size // THREADS
    threads = []
    parts = []

    with Progress() as progress:
        task_id = progress.add_task("Downloading", total=file_size)

        for i in range(THREADS):
            start = part_size * i
            # 最後のパートはファイルの終わりまで
            end = file_size - 1 if i == THREADS - 1 else start + part_size - 1
            parts.append(f"{OUTPUT_FILE}.part{i}")
            thread = Thread(target=download_range, args=(URL, start, end, i, progress, task_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    # パーツを結合
    try:
        merge_files(parts, OUTPUT_FILE)
        console.print(f"[green]Download completed: {OUTPUT_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Error merging files: {e}[/red]")

if __name__ == "__main__":
    main()

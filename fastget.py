import os
import requests
from tqdm import tqdm
from threading import Thread

# ダウンロードするファイルのURL
URL = input("URL: ")

# 保存先ファイル名
OUTPUT_FILE = os.path.basename(URL)

# スレッド数（同時接続数）
THREADS = 8

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

def download_range(url, start, end, part_num, progress, headers=None):
    """
    指定された範囲をダウンロードする関数
    """
    headers = headers or {}
    headers.update({'Range': f'bytes={start}-{end}'})
    response = requests.get(url, headers=headers, stream=True)
    with open(f"{OUTPUT_FILE}.part{part_num}", 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))

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
        print(f"Error: {e}")
        return

    if not is_resumable:
        print("Server is not supported multiple threads. Downloading in single thread...")
        THREADS = 1

    part_size = file_size // THREADS
    threads = []
    parts = []
    progress = tqdm(total=file_size, unit='B', unit_scale=True, desc=OUTPUT_FILE)

    for i in range(THREADS):
        start = part_size * i
        # 最後のパートはファイルの終わりまで
        end = file_size if i == THREADS - 1 else start + part_size - 1
        parts.append(f"{OUTPUT_FILE}.part{i}")
        thread = Thread(target=download_range, args=(URL, start, end, i, progress))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    progress.close()

    # パーツを結合
    merge_files(parts, OUTPUT_FILE)
    print(f"ダウンロードが完了しました: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

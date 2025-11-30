import os
import math
import argparse
import asyncio
from . import fastget
from nercone_modern.logging import ModernLogging
from nercone_modern.progressbar import ModernProgressBar

class CLIProgress(fastget.ProgressCallback):
    def __init__(self, logger: ModernLogging):
        self.logger = logger
        self.all_bar = None
        self.thread_bars = []
        self.chunk_size_display = 1024 * 128
        self.merge_accumulated = 0

    async def on_start(self, total_size: int, connections: int) -> None:
        self.logger.log(f"Starting: {total_size:,} bytes (Connections: {connections})")

        if total_size > 0:
            total_steps = max(1, math.ceil(total_size / self.chunk_size_display))
            self.all_bar = ModernProgressBar(
                total=total_steps, 
                process_name="Total", 
                spinner_mode=False, 
                show_vertical_bar=True
            )
            self.all_bar.start()

            if connections > 1:
                part_size = total_size // connections
                for i in range(connections):
                    p_steps = max(1, math.ceil(part_size / self.chunk_size_display))
                    bar = ModernProgressBar(
                        total=p_steps, 
                        process_name=f"Conn #{i+1}", 
                        spinner_mode=False, 
                        show_vertical_bar=True
                    )
                    bar.start()
                    self.thread_bars.append(bar)

    async def on_update(self, worker_id: int, loaded: int) -> None:
        if self.thread_bars and worker_id < len(self.thread_bars):
            self.thread_bars[worker_id].update()

        if self.all_bar:
            self.all_bar.update()

    async def on_complete(self) -> None:
        if self.all_bar:
            self.all_bar.finish()

        for b in self.thread_bars:
            b.finish()

    async def on_merge_start(self, total_size: int) -> None:
        self.merge_accumulated = 0
        if total_size > 0:
            total_steps = max(1, math.ceil(total_size / self.chunk_size_display))
            self.merge_bar = ModernProgressBar(
                total=total_steps,
                process_name="Merge",
                spinner_mode=False,
                show_vertical_bar=True
            )
            self.merge_bar.start()

    async def on_merge_update(self, loaded: int) -> None:
        if self.merge_bar:
            self.merge_accumulated += loaded
            while self.merge_accumulated >= self.chunk_size_display:
                self.merge_bar.update()
                self.merge_accumulated -= self.chunk_size_display

    async def on_merge_complete(self) -> None:
        if self.merge_bar:
            self.merge_bar.finish()

    async def on_error(self, msg: str) -> None:
        self.logger.log(msg, "ERROR")

async def async_main() -> None:
    logger = ModernLogging("fastget", show_level=False, show_proc=False)

    parser = argparse.ArgumentParser(prog='fastget', description='FastGet: Modern High-Performance Downloader')
    parser.add_argument('url', help="Target URL")
    parser.add_argument('-o', '--output', help="Write output to <file>")
    parser.add_argument('-X', '--request', default='GET', help="Specify request method")
    parser.add_argument('-d', '--data', help="HTTP POST data")
    parser.add_argument('-H', '--header', action='append', help="Pass custom header(s)")
    parser.add_argument('-t', '--threads', dest='concurrency', type=int, default=fastget.DEFAULT_CONCURRENCY, help="Number of concurrent connections")
    parser.add_argument('--no-http2', action='store_true', help="Disable HTTP/2")
    parser.add_argument('--no-verify', action='store_true', help="Disable SSL verification")
    parser.add_argument('--memory', action='store_true', help="Fetch to memory")

    args = parser.parse_args()

    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()

    method = args.request
    if args.data and method == 'GET':
        method = 'POST'

    output = args.output
    if not output and not args.memory:
        parsed = fastget.urlparse(args.url)
        output = fastget.unquote(os.path.basename(parsed.path)) or "downloaded_file"

    callback = CLIProgress(logger)

    session = fastget.FastGetSession(
        max_concurrency=args.concurrency,
        http2=not args.no_http2,
        verify=not args.no_verify
    )

    start_time = asyncio.get_running_loop().time()

    try:
        if args.memory:
            result = await session.process(
                method=method, 
                url=args.url, 
                data=args.data, 
                headers=headers, 
                callback=callback
            )
            print(result.text)
        else:
            path = await session.process(
                method=method, 
                url=args.url, 
                output=output, 
                data=args.data, 
                headers=headers, 
                callback=callback
            )
            end_time = asyncio.get_running_loop().time()
            duration_ms = (end_time - start_time) * 1000

            logger.log(f"Completed in {duration_ms:.2f}ms")
            logger.log(f"Saved to: {path}")

    except fastget.FastGetError as e:
        logger.log(str(e), "CRITICAL")
    except Exception as e:
        logger.log(f"Unexpected error: {e}", "CRITICAL")

def main() -> None:
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

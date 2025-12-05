import os
import asyncio
import httpx
from importlib.metadata import version
from typing import Union, Optional, Dict, Any, TypeVar, Coroutine, Awaitable
from urllib.parse import urlparse, unquote

try:
    VERSION = version("nercone-fastget")
except Exception:
    VERSION = "0.0.0"

DEFAULT_CHUNK_SIZE = 1024 * 64
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
DEFAULT_THREADS = 8

T = TypeVar("T")

class FastGetError(Exception):
    pass

class ProgressCallback:
    async def on_start(self, total_size: int, threads: int, http_version: str, final_url: str, verify_was_enabled: bool) -> None:
        pass

    async def on_update(self, worker_id: int, loaded: int) -> None:
        pass

    async def on_complete(self) -> None:
        pass

    async def on_merge_start(self, total_size: int) -> None:
        pass

    async def on_merge_update(self, loaded: int) -> None:
        pass

    async def on_merge_complete(self) -> None:
        pass

    async def on_error(self, msg: str) -> None:
        pass

class FastGetResponse:
    def __init__(self, original: httpx.Response, content: bytes):
        self._r = original
        self.content = content
        self.url = str(original.url)
        self.status_code = original.status_code
        self.headers = original.headers
        self.http_version = original.http_version

    @property
    def text(self) -> str:
        return self._r.text

    def json(self, **kwargs) -> Any:
        return self._r.json(**kwargs)

class FastGetSession:
    def __init__(self, max_threads: int = DEFAULT_THREADS, http2: bool = True, verify: bool = True, follow_redirects: bool = True):
        self.max_threads = max_threads
        self.client_args = {
            "http2": http2,
            "verify": verify,
            "follow_redirects": follow_redirects,
            "timeout": DEFAULT_TIMEOUT
        }

    async def _get_info(self, client: httpx.AsyncClient, method: str, url: str, **kwargs) -> tuple[int, bool, bool, Optional[httpx.Response]]:
        headers = kwargs.get("headers", {}).copy()
        headers["User-Agent"] = f'FastGet/{VERSION} (Getting Informations, https://github.com/DiamondGotCat/nercone-fastget)'

        if method.upper() != "GET":
            return 0, False, False, None

        try:
            head_resp = await client.head(url, headers=headers)

            if head_resp.status_code < 400:
                resp = head_resp
            else:
                resp = await client.request(method, url, headers=headers, stream=True)
                await resp.aclose()

            size = int(resp.headers.get("content-length", 0))
            accept_ranges = resp.headers.get("accept-ranges", "").lower() == "bytes"
            reject_fg = resp.headers.get("rejectfastget", "").lower() in ["true", "1", "yes"]

            return size, accept_ranges, reject_fg, resp

        except Exception:
            return 0, False, True, None

    async def _download_worker(self, client: httpx.AsyncClient, method: str, url: str, start: int, end: int, worker_id: int, total_threads: int, part_path: str, callback: ProgressCallback, **kwargs) -> None:
        headers = kwargs.get("headers", {}).copy()
        headers["Range"] = f"bytes={start}-{end}"
        headers["User-Agent"] = f'FastGet/{VERSION} (Downloading with {total_threads} Thread(s), Connection No. {worker_id}, https://github.com/DiamondGotCat/nercone-fastget)'
        kwargs["headers"] = headers

        for attempt in range(DEFAULT_RETRIES):
            try:
                async with client.stream(method, url, **kwargs) as response:
                    response.raise_for_status()

                    with open(part_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=DEFAULT_CHUNK_SIZE):
                            if not chunk:
                                break
                            
                            f.write(chunk)
                            await callback.on_update(worker_id, len(chunk))
                return

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == DEFAULT_RETRIES - 1:
                    await callback.on_error(f"Worker {worker_id} failed: {e}")
                    raise
                await asyncio.sleep(1)

    async def process(self, method: str, url: str, output: Optional[str] = None, data: Any = None, json: Any = None, params: Any = None, headers: Dict = None, callback: Optional[ProgressCallback] = None) -> Union[str, FastGetResponse]:
        callback = callback or ProgressCallback()
        if headers is None:
            headers = {}

        req_kwargs = {"data": data, "json": json, "params": params, "headers": headers}

        async with httpx.AsyncClient(**self.client_args) as client:
            file_size, is_resumable, is_rejected, info_response = await self._get_info(client, method, url, **req_kwargs)

            if method.upper() == "GET" and not info_response:
                raise FastGetError(f"Failed to retrieve file information from {url}")

            use_parallel = (
                method.upper() == "GET" and 
                is_resumable and 
                not is_rejected and 
                file_size > 0 and 
                output is not None
            )

            threads = self.max_threads if use_parallel else 1

            http_version = info_response.http_version if info_response else "HTTP/1.1"
            final_url = str(info_response.url) if info_response else url

            await callback.on_start(
                total_size=file_size,
                threads=threads,
                http_version=http_version,
                final_url=final_url,
                verify_was_enabled=self.client_args["verify"]
            )

            if output:
                out_dir = os.path.dirname(output)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)

                if use_parallel:
                    part_size = file_size // threads
                    tasks = []
                    part_files = []

                    for i in range(threads):
                        start = part_size * i
                        end = file_size - 1 if i == threads - 1 else start + part_size - 1
                        
                        part_path = f"{output}.part{i}"
                        part_files.append(part_path)

                        tasks.append(
                            self._download_worker(
                                client, method, url, start, end, i, threads, part_path, callback, **req_kwargs
                            )
                        )

                    await asyncio.gather(*tasks)

                    await callback.on_merge_start(file_size)
                    with open(output, "wb") as outfile:
                        for part_file in part_files:
                            if os.path.exists(part_file):
                                with open(part_file, "rb") as infile:
                                    while True:
                                        chunk = infile.read(DEFAULT_CHUNK_SIZE)
                                        if not chunk:
                                            break
                                        outfile.write(chunk)
                                        await callback.on_merge_update(len(chunk))
                                os.remove(part_file)

                    await callback.on_merge_complete()

                else:
                    headers["User-Agent"] = f'FastGet/{VERSION} (Downloading with 1 Thread(s), Connection No. 0, https://github.com/DiamondGotCat/nercone-fastget)'
                    async with client.stream(method, url, **req_kwargs) as response:
                        response.raise_for_status()
                        with open(output, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=DEFAULT_CHUNK_SIZE):
                                f.write(chunk)
                                await callback.on_update(0, len(chunk))

                await callback.on_complete()
                return output

            else:
                content_buffer = bytearray()
                response_obj = None
                headers["User-Agent"] = f'FastGet/{VERSION} (Downloading with 1 Thread(s), Connection No. 0, https://github.com/DiamondGotCat/nercone-fastget)'

                async with client.stream(method, url, **req_kwargs) as response:
                    response.raise_for_status()
                    response_obj = response
                    async for chunk in response.aiter_bytes(chunk_size=DEFAULT_CHUNK_SIZE):
                        content_buffer.extend(chunk)
                        await callback.on_update(0, len(chunk))

                await callback.on_complete()

                final_response = httpx.Response(
                    status_code=response_obj.status_code,
                    headers=response_obj.headers,
                    request=response_obj.request,
                    content=bytes(content_buffer)
                )
                return FastGetResponse(final_response, bytes(content_buffer))

def run_sync(coro: Awaitable[T]) -> T:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def download(url: str, output: str, **kwargs) -> str:
    session = FastGetSession(
        max_threads=kwargs.pop("threads", DEFAULT_THREADS),
        http2=not kwargs.pop("no_http2", False)
    )
    return run_sync(session.process("GET", url, output=output, **kwargs))

def request(method: str, url: str, **kwargs) -> FastGetResponse:
    session = FastGetSession(
        max_threads=kwargs.pop("threads", DEFAULT_THREADS),
        http2=not kwargs.pop("no_http2", False)
    )
    return run_sync(session.process(method, url, output=None, **kwargs))

def get(url: str, **kwargs) -> FastGetResponse:
    return request("GET", url, **kwargs)

def post(url: str, **kwargs) -> FastGetResponse:
    return request("POST", url, **kwargs)

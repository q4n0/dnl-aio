#!/usr/bin/env python3

import os
import sys
import logging
import platform
import tempfile
import urllib.request
import zipfile
import hashlib
import asyncio
import aiohttp
import aiofiles
import uvloop
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Enable uvloop for better async performance on Unix systems
if sys.platform != 'win32':
    uvloop.install()

@dataclass
class DownloadConfig:
    chunk_size: int = 1024 * 1024  # 1MB default chunk size
    max_concurrent_downloads: int = 3
    max_retries: int = 3
    connection_timeout: int = 30
    read_timeout: int = 30
    max_connections_per_file: int = 16
    verify_ssl: bool = True
    follow_redirects: bool = True
    user_agent: str = "Python-Downloader/1.0"
    proxy: Optional[str] = None
    buffer_size: int = 8192  # 8KB buffer size for file operations

class DownloadError(Exception):
    """Custom exception for download-related errors"""
    pass

class SystemInfo:
    def __init__(self):
        self.platform = platform.system().lower()
        self.is_windows = self.platform == 'windows'
        self.is_mac = self.platform == 'darwin'
        self.is_linux = self.platform == 'linux'
        self.cpu_count = os.cpu_count() or 1
        self.memory_info = self._get_memory_info()
        self.temp_dir = tempfile.gettempdir()
        self.python_version = sys.version_info
        self.is_64bit = sys.maxsize > 2**32

    def _get_memory_info(self) -> Dict[str, int]:
        """Get system memory information"""
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {
                'total': vm.total,
                'available': vm.available,
                'used': vm.used,
                'free': vm.free
            }
        except ImportError:
            return {
                'total': 0,
                'available': 0,
                'used': 0,
                'free': 0
            }

    def get_optimal_chunk_size(self) -> int:
        """Calculate optimal chunk size based on system memory"""
        available_memory = self.memory_info['available']
        if available_memory > 0:
            # Use 1% of available memory, min 1MB, max 16MB
            chunk_size = max(min(available_memory // 100, 16 * 1024 * 1024), 1024 * 1024)
            return chunk_size
        return 1024 * 1024  # Default to 1MB if memory info unavailable

    def get_optimal_connections(self) -> int:
        """Calculate optimal number of connections based on CPU cores"""
        return min(max(self.cpu_count * 2, 4), 16)

class AsyncDownloader:
    def __init__(self, config: Optional[DownloadConfig] = None):
        self.config = config or DownloadConfig()
        self.system_info = SystemInfo()
        self.session: Optional[aiohttp.ClientSession] = None
        self.executor = ThreadPoolExecutor(
            max_workers=self.system_info.cpu_count,
            thread_name_prefix="download_worker"
        )
        self.console = Console()
        self.active_downloads: Dict[str, Any] = {}

    async def __aenter__(self):
        """Context manager entry"""
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.config.connection_timeout,
            sock_read=self.config.read_timeout
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={'User-Agent': self.config.user_agent}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
        self.executor.shutdown(wait=True)

    async def get_file_info(self, url: str) -> Dict[str, Any]:
        """Get file information asynchronously"""
        if not self.session:
            raise DownloadError("Session not initialized")

        try:
            async with self.session.head(url, allow_redirects=True) as response:
                response.raise_for_status()
                
                return {
                    'size': int(response.headers.get('content-length', 0)),
                    'resume_support': 'accept-ranges' in response.headers,
                    'type': response.headers.get('content-type', 'application/octet-stream'),
                    'filename': Path(response.url.name).name,
                    'etag': response.headers.get('etag'),
                    'last_modified': response.headers.get('last-modified')
                }
        except Exception as e:
            raise DownloadError(f"Failed to get file info: {str(e)}")

    async def download_chunk(
        self,
        url: str,
        start: int,
        end: int,
        file,
        progress: Optional[Progress] = None,
        task_id: Optional[str] = None
    ) -> int:
        """Download a specific chunk of a file"""
        if not self.session:
            raise DownloadError("Session not initialized")

        headers = {'Range': f'bytes={start}-{end}'}
        bytes_downloaded = 0

        try:
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                
                async for chunk in response.content.iter_chunked(self.config.chunk_size):
                    bytes_downloaded += len(chunk)
                    await file.seek(start + bytes_downloaded - len(chunk))
                    await file.write(chunk)
                    
                    if progress and task_id:
                        progress.update(task_id, advance=len(chunk))

            return bytes_downloaded

        except Exception as e:
            raise DownloadError(f"Chunk download failed: {str(e)}")

    @staticmethod
    def calculate_chunks(file_size: int, connections: int) -> list:
        """Calculate chunk ranges for parallel downloading"""
        chunk_size = file_size // connections
        chunks = []
        
        for i in range(connections):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < connections - 1 else file_size - 1
            chunks.append((start, end))
            
        return chunks

    async def download_file(
        self,
        url: str,
        output_path: Union[str, Path],
        connections: Optional[int] = None
    ) -> bool:
        """Download a file with multiple connections and progress tracking"""
        try:
            # Get file information
            file_info = await self.get_file_info(url)
            file_size = file_info['size']
            
            if not file_size:
                raise DownloadError("File size unknown")

            # Use optimal or specified connections
            connections = connections or self.system_info.get_optimal_connections()
            
            # Prepare output path
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Calculate chunks for parallel download
            chunks = self.calculate_chunks(file_size, connections)
            
            async with aiofiles.open(output_path, 'wb') as file:
                # Pre-allocate file
                await file.truncate(file_size)
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("[cyan]{task.fields[speed]}"),
                    TimeRemainingColumn(),
                    console=self.console
                ) as progress:
                    # Create main progress task
                    task_id = progress.add_task(
                        f"Downloading {Path(url).name}",
                        total=file_size,
                        speed="0 MB/s"
                    )
                    
                    # Create tasks for parallel downloads
                    chunk_tasks = [
                        self.download_chunk(url, start, end, file, progress, task_id)
                        for start, end in chunks
                    ]
                    
                    # Execute downloads in parallel
                    results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
                    
                    # Check for errors
                    errors = [r for r in results if isinstance(r, Exception)]
                    if errors:
                        raise DownloadError(f"Download failed: {errors[0]}")
                    
                    # Verify downloaded size
                    total_downloaded = sum(r for r in results if isinstance(r, int))
                    if total_downloaded != file_size:
                        raise DownloadError("Download size mismatch")

            return True

        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            if output_path.exists():
                output_path.unlink()
            return False

    def verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Verify file integrity using SHA-256 checksum"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(self.config.buffer_size), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest() == expected_checksum
        except Exception as e:
            logger.error(f"Checksum verification failed: {str(e)}")
            return False

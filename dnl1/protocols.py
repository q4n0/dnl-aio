# protocols.py

import os
import asyncio
import aiohttp
import aiofiles
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, unquote
import libtorrent as lt
import yt_dlp
from rich.progress import Progress

from core import DownloadError, AsyncDownloader, DownloadConfig

@dataclass
class DownloadInfo:
    url: str
    file_type: str
    status: str
    progress: float
    started_at: datetime
    completed_at: Optional[datetime]
    file_size: Optional[int]
    download_path: Path
    checksum: Optional[str]
    speed: Optional[str]
    error: Optional[str]
    metadata: Dict[str, Any]

class ProtocolHandler(ABC):
    """Base class for protocol handlers"""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.downloader = AsyncDownloader(config)

    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this handler can process the URL"""
        pass

    @abstractmethod
    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        """Download the file and return download information"""
        pass

class HTTPHandler(ProtocolHandler):
    """Handler for HTTP/HTTPS downloads"""

    async def can_handle(self, url: str) -> bool:
        return url.startswith(('http://', 'https://'))

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='http',
            status='starting',
            progress=0.0,
            started_at=datetime.now(),
            completed_at=None,
            file_size=None,
            download_path=output_path,
            checksum=None,
            speed=None,
            error=None,
            metadata={}
        )

        try:
            async with self.downloader:
                # Get file information
                file_info = await self.downloader.get_file_info(url)
                download_info.file_size = file_info['size']
                download_info.metadata = file_info

                # Start download
                download_info.status = 'downloading'
                success = await self.downloader.download_file(
                    url,
                    output_path,
                    self.config.max_connections_per_file
                )

                if success:
                    download_info.status = 'completed'
                    download_info.progress = 100.0
                    download_info.completed_at = datetime.now()
                else:
                    download_info.status = 'failed'
                    download_info.error = 'Download failed'

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"HTTP download failed: {str(e)}")

        return download_info

class TorrentHandler(ProtocolHandler):
    """Handler for torrent downloads"""

    async def can_handle(self, url: str) -> bool:
        return url.startswith('magnet:') or url.endswith('.torrent')

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='torrent',
            status='starting',
            progress=0.0,
            started_at=datetime.now(),
            completed_at=None,
            file_size=None,
            download_path=output_path,
            checksum=None,
            speed=None,
            error=None,
            metadata={}
        )

        try:
            # Initialize libtorrent session
            session = lt.session()
            session.listen_on(6881, 6891)

            # Add torrent
            if url.startswith('magnet:'):
                handle = lt.add_magnet_uri(session, url, {
                    'save_path': str(output_path),
                    'storage_mode': lt.storage_mode_t(2)
                })
                handle.set_sequential_download(True)
            else:
                info = lt.torrent_info(url)
                handle = session.add_torrent({
                    'ti': info,
                    'save_path': str(output_path),
                    'storage_mode': lt.storage_mode_t(2)
                })

            download_info.status = 'downloading'
            task_id = progress.add_task(
                "Downloading torrent",
                total=100,
                speed="0 MB/s"
            )

            while not handle.is_seed():
                status = handle.status()
                download_info.progress = status.progress * 100
                download_info.speed = f"{status.download_rate / 1024 / 1024:.2f} MB/s"
                
                progress.update(
                    task_id,
                    completed=download_info.progress,
                    speed=download_info.speed
                )

                # Update metadata
                download_info.metadata.update({
                    'peers': status.num_peers,
                    'seeds': status.num_seeds,
                    'state': str(status.state)
                })

                await asyncio.sleep(1)

            download_info.status = 'completed'
            download_info.progress = 100.0
            download_info.completed_at = datetime.now()

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"Torrent download failed: {str(e)}")

        return download_info

class YouTubeHandler(ProtocolHandler):
    """Handler for YouTube downloads"""

    async def can_handle(self, url: str) -> bool:
        try:
            extractors = yt_dlp.extractor.gen_extractors()
            for e in extractors:
                if e.suitable(url) and e.IE_NAME != 'generic':
                    return True
            return False
        except:
            return False

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='youtube',
            status='starting',
            progress=0.0,
            started_at=datetime.now(),
            completed_at=None,
            file_size=None,
            download_path=output_path,
            checksum=None,
            speed=None,
            error=None,
            metadata={}
        )

        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    download_info.progress = float(d['_percent_str'].replace('%', ''))
                    download_info.speed = d.get('_speed_str', 'N/A')
                    progress.update(
                        task_id,
                        completed=download_info.progress,
                        speed=download_info.speed
                    )

            ydl_opts = {
                'format': 'best',
                'outtmpl': str(output_path / '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True
            }

            task_id = progress.add_task(
                "Downloading YouTube video",
                total=100,
                speed="0 MB/s"
            )

            download_info.status = 'downloading'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video information
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                download_info.metadata = {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'format': info.get('format'),
                    'resolution': info.get('resolution')
                }
                
                # Download video
                await asyncio.to_thread(ydl.download, [url])

            download_info.status = 'completed'
            download_info.progress = 100.0
            download_info.completed_at = datetime.now()

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"YouTube download failed: {str(e)}")

        return download_info

class DownloadTracker:
    """Track and manage downloads"""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / '.downloads'
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_path / 'history.json'
        self.active_downloads: Dict[str, DownloadInfo] = {}
        self.history: List[Dict[str, Any]] = self.load_history()

    def load_history(self) -> List[Dict[str, Any]]:
        """Load download history from file"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading history: {e}")
            return []

    def save_history(self):
        """Save download history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving history: {e}")

    def add_download(self, download_info: DownloadInfo):
        """Add a download to tracking"""
        self.active_downloads[download_info.url] = download_info
        self.history.append(asdict(download_info))
        self.save_history()

    def update_download(self, url: str, **kwargs):
        """Update download information"""
        if url in self.active_downloads:
            download_info = self.active_downloads[url]
            for key, value in kwargs.items():
                setattr(download_info, key, value)
            
            # Update history
            for entry in self.history:
                if entry['url'] == url:
                    entry.update(asdict(download_info))
                    break
            
            self.save_history()

    def get_download_info(self, url: str) -> Optional[DownloadInfo]:
        """Get information about a specific download"""
        return self.active_downloads.get(url)

    def get_active_downloads(self) -> List[DownloadInfo]:
        """Get list of active downloads"""
        return list(self.active_downloads.values())

    def get_download_history(self) -> List[Dict[str, Any]]:
        """Get complete download history"""
        return self.history

    def clear_history(self):
        """Clear download history"""
        self.history = []
        self.save_history()

class ProtocolManager:
    """Manage protocol handlers"""

    def __init__(self, config: DownloadConfig):
        self.handlers = [
            HTTPHandler(config),
            TorrentHandler(config),
            YouTubeHandler(config)
        ]

    async def get_handler(self, url: str) -> Optional[ProtocolHandler]:
        """Get appropriate handler for URL"""
        for handler in self.handlers:
            if await handler.can_handle(url):
                return handler
        return None

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        """Download using appropriate handler"""
        handler = await self.get_handler(url)
        if not handler:
            raise DownloadError(f"No handler found for URL: {url}")
        return await handler.download(url, output_path, progress)

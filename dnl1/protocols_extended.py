# protocols_extended.py

import asyncio
import aiohttp
import asyncssh
import aioftp
import aiowebdav.client
import paramiko
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from protocols import ProtocolHandler, DownloadInfo
from rich.progress import Progress

class SFTPHandler(ProtocolHandler):
    """Handler for SFTP downloads"""
    
    async def can_handle(self, url: str) -> bool:
        return url.startswith(('sftp://', 'ssh://'))

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='sftp',
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
            # Parse URL
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            port = parsed.port or 22
            path = parsed.path
            username = parsed.username
            password = parsed.password

            async with asyncssh.connect(
                host,
                port=port,
                username=username,
                password=password
            ) as conn:
                async with conn.start_sftp_client() as sftp:
                    # Get file info
                    file_attrs = await sftp.stat(path)
                    file_size = file_attrs.size
                    download_info.file_size = file_size

                    # Create progress bar
                    task_id = progress.add_task(
                        "Downloading via SFTP",
                        total=file_size,
                        speed="0 MB/s"
                    )

                    # Download with progress
                    start_time = time.time()
                    bytes_downloaded = 0

                    async with output_path.open('wb') as f:
                        async for chunk in sftp.read(path, block_size=self.config.chunk_size):
                            bytes_downloaded += len(chunk)
                            await f.write(chunk)
                            
                            # Update progress
                            progress.update(
                                task_id,
                                completed=bytes_downloaded,
                                speed=f"{bytes_downloaded/(time.time()-start_time)/1024/1024:.2f} MB/s"
                            )

                    download_info.status = 'completed'
                    download_info.progress = 100.0
                    download_info.completed_at = datetime.now()

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"SFTP download failed: {str(e)}")

        return download_info

class WebDAVHandler(ProtocolHandler):
    """Handler for WebDAV downloads"""
    
    async def can_handle(self, url: str) -> bool:
        return url.startswith(('webdav://', 'dav://'))

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='webdav',
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
            parsed = urllib.parse.urlparse(url)
            client = aiowebdav.client.Client(
                parsed.hostname,
                port=parsed.port or 443,
                protocol='https' if parsed.scheme == 'webdav' else 'http'
            )

            if parsed.username and parsed.password:
                await client.set_basic_auth(parsed.username, parsed.password)

            # Get file info
            file_info = await client.info(parsed.path)
            file_size = int(file_info.get('getcontentlength', 0))
            download_info.file_size = file_size

            task_id = progress.add_task(
                "Downloading via WebDAV",
                total=file_size,
                speed="0 MB/s"
            )

            async with output_path.open('wb') as f:
                async for chunk in client.download(parsed.path):
                    await f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

            download_info.status = 'completed'
            download_info.progress = 100.0
            download_info.completed_at = datetime.now()

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"WebDAV download failed: {str(e)}")

        return download_info

class FTPHandler(ProtocolHandler):
    """Handler for FTP downloads"""
    
    async def can_handle(self, url: str) -> bool:
        return url.startswith('ftp://')

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='ftp',
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
            parsed = urllib.parse.urlparse(url)
            async with aioftp.Client.context(
                parsed.hostname,
                port=parsed.port or 21,
                user=parsed.username or 'anonymous',
                password=parsed.password or 'anonymous@'
            ) as client:
                # Get file size
                file_size = await client.stat(parsed.path).get('size', 0)
                download_info.file_size = file_size

                task_id = progress.add_task(
                    "Downloading via FTP",
                    total=file_size,
                    speed="0 MB/s"
                )

                start_time = time.time()
                bytes_downloaded = 0

                async with output_path.open('wb') as f:
                    async for chunk in client.download_stream(parsed.path):
                        bytes_downloaded += len(chunk)
                        await f.write(chunk)
                        
                        # Update progress
                        progress.update(
                            task_id,
                            completed=bytes_downloaded,
                            speed=f"{bytes_downloaded/(time.time()-start_time)/1024/1024:.2f} MB/s"
                        )

                download_info.status = 'completed'
                download_info.progress = 100.0
                download_info.completed_at = datetime.now()

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"FTP download failed: {str(e)}")

        return download_info

class M3U8Handler(ProtocolHandler):
    """Handler for M3U8/HLS streams"""
    
    async def can_handle(self, url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    content = await response.text()
                    return content.startswith('#EXTM3U')
        except:
            return False

    async def download(self, url: str, output_path: Path, progress: Progress) -> DownloadInfo:
        download_info = DownloadInfo(
            url=url,
            file_type='m3u8',
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
            import m3u8
            playlist = m3u8.load(url)
            
            if playlist.is_endlist:
                total_segments = len(playlist.segments)
                download_info.file_size = total_segments
                
                task_id = progress.add_task(
                    "Downloading M3U8 stream",
                    total=total_segments,
                    speed="0 segments/s"
                )

                temp_dir = output_path.parent / f"{output_path.stem}_segments"
                temp_dir.mkdir(exist_ok=True)
                
                segment_files = []
                async with aiohttp.ClientSession() as session:
                    for i, segment in enumerate(playlist.segments):
                        segment_url = segment.absolute_uri
                        segment_path = temp_dir / f"segment_{i:05d}.ts"
                        
                        async with session.get(segment_url) as response:
                            content = await response.read()
                            async with aiofiles.open(segment_path, 'wb') as f:
                                await f.write(content)
                        
                        segment_files.append(segment_path)
                        progress.update(task_id, completed=i+1)

                # Merge segments
                with output_path.open('wb') as outfile:
                    for segment_file in segment_files:
                        outfile.write(segment_file.read_bytes())
                        segment_file.unlink()

                temp_dir.rmdir()
                
                download_info.status = 'completed'
                download_info.progress = 100.0
                download_info.completed_at = datetime.now()

            else:
                raise DownloadError("Live streams are not supported")

        except Exception as e:
            download_info.status = 'failed'
            download_info.error = str(e)
            raise DownloadError(f"M3U8 download failed: {str(e)}")

        return download_info

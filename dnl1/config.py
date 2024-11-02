# config.py

import os
import yaml
import json
import configparser
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from rich.console import Console

@dataclass
class AdvancedConfig:
    # Network settings
    bandwidth_limit: Optional[int] = None  # In bytes/second
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    dns_servers: list = None
    timeout: int = 30
    retry_attempts: int = 3
    verify_ssl: bool = True

    # Performance settings
    buffer_size: int = 8192
    chunk_size: int = 1024 * 1024
    max_concurrent_downloads: int = 3
    connections_per_file: int = 16
    use_threading: bool = True
    use_asyncio: bool = True

    # Storage settings
    temp_directory: Optional[str] = None
    download_directory: Optional[str] = None
    organize_by_type: bool = True
    preserve_metadata: bool = True
    verify_downloads: bool = True

    # Protocol specific settings
    youtube_quality: str = 'best'
    torrent_port_range: tuple = (6881, 6889)
    torrent_seed_ratio: float = 0.0
    torrent_seed_time: int = 0

class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.console = Console()
        self.config_dir = config_dir or Path.home() / '.config' / 'downloader'
        self.config_file = self.config_dir / 'config.yaml'
        self.config = self.load_config()

    def load_config(self) -> AdvancedConfig:
        """Load configuration from file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config_file.exists():
                with open(self.config_file) as f:
                    config_data = yaml.safe_load(f)
                return AdvancedConfig(**config_data)
            
            # Create default config if not exists
            config = AdvancedConfig()
            self.save_config(config)
            return config

        except Exception as e:
            self.console.print(f"[yellow]Error loading config: {e}. Using defaults.[/yellow]")
            return AdvancedConfig()

    def save_config(self, config: AdvancedConfig):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                yaml.safe_dump(asdict(config), f, default_flow_style=False)
        except Exception as e:
            self.console.print(f"[red]Error saving config: {e}[/red]")

class BandwidthManager:
    """Manage download bandwidth"""
    
    def __init__(self, limit: Optional[int] = None):
        self.limit = limit
        self._current_speed = 0
        self._last_update = 0
        self._bytes_transferred = 0

    def update(self, bytes_transferred: int):
        """Update bandwidth tracking"""
        import time
        current_time = time.time()
        
        if self._last_update == 0:
            self._last_update = current_time
            return
        
        time_diff = current_time - self._last_update
        if time_diff > 0:
            self._current_speed = bytes_transferred / time_diff
            self._last_update = current_time
            self._bytes_transferred = 0

    async def limit_bandwidth(self, bytes_to_transfer: int) -> int:
        """Limit bandwidth if needed"""
        if not self.limit:
            return bytes_to_transfer

        import asyncio
        if self._current_speed > self.limit:
            delay = (self._current_speed - self.limit) / self.limit
            await asyncio.sleep(delay)
            return min(bytes_to_transfer, self.limit)
        
        return bytes_to_transfer

class DownloadOptimizer:
    """Optimize download performance"""
    
    def __init__(self, config: AdvancedConfig):
        self.config = config
        self.system_info = SystemInfo()

    def get_optimal_chunk_size(self) -> int:
        """Calculate optimal chunk size based on system memory"""
        memory_info = self.system_info.memory_info
        available_memory = memory_info['available']
        
        if available_memory > 0:
            # Use 1% of available memory, min 1MB, max 16MB
            chunk_size = max(min(available_memory // 100, 16 * 1024 * 1024), 1024 * 1024)
            return chunk_size
        
        return self.config.chunk_size

    def get_optimal_connections(self) -> int:
        """Calculate optimal number of connections"""
        cpu_count = self.system_info.cpu_count
        return min(max(cpu_count * 2, 4), 16)

    def optimize_settings(self) -> AdvancedConfig:
        """Optimize all settings based on system capabilities"""
        self.config.chunk_size = self.get_optimal_chunk_size()
        self.config.connections_per_file = self.get_optimal_connections()
        
        # Adjust concurrent downloads based on available memory
        memory_info = self.system_info.memory_info
        if memory_info['available'] < 1024 * 1024 * 1024:  # Less than 1GB
            self.config.max_concurrent_downloads = 1
        elif memory_info['available'] < 4 * 1024 * 1024 * 1024:  # Less than 4GB
            self.config.max_concurrent_downloads = 2
        
        return self.config

"""
USAGE DOCUMENTATION

Quick Start:
------------
1. Basic Download:
   ```python
   from downloader.cli import DownloadCLI
   
   cli = DownloadCLI()
   asyncio.run(cli.run())
   ```

2. Command Line Usage:
   ```bash
   python3 downloader.py <url> [options]
   ```

Advanced Usage:
--------------
1. Custom Configuration:
   ```python
   from downloader.config import ConfigManager, AdvancedConfig
   
   config = AdvancedConfig(
       bandwidth_limit=1024*1024,  # 1MB/s
       max_concurrent_downloads=5
   )
   
   manager = ConfigManager()
   manager.save_config(config)
   ```

2. Batch Downloads:
   ```python
   urls = ['url1', 'url2', 'url3']
   output_path = Path('downloads')
   results = await cli.batch_download(urls, output_path)
   ```

3. Performance Optimization:
   ```python
   from downloader.config import DownloadOptimizer
   
   optimizer = DownloadOptimizer(config)
   optimized_config = optimizer.optimize_settings()
   ```

Features:
---------
1. Multiple Protocol Support:
   - HTTP/HTTPS
   - FTP/SFTP
   - Torrent (Magnet/File)
   - YouTube
   - Direct Downloads

2. Performance:
   - Async Downloads
   - Multi-connection Support
   - Bandwidth Control
   - Auto-optimization

3. Management:
   - Download History
   - Progress Tracking
   - Resume Support
   - Integrity Verification

4. Configuration:
   - Custom Settings
   - Profile Support
   - Proxy Configuration
   - Bandwidth Limits

Examples:
---------
1. Download with Bandwidth Limit:
   ```python
   config.bandwidth_limit = 1024 * 1024  # 1MB/s
   await cli.download_file('http://example.com/file.zip', Path('downloads'))
   ```

2. YouTube Download:
   ```python
   config.youtube_quality = '1080p'
   await cli.download_file('https://youtube.com/watch?v=...', Path('downloads'))
   ```

3. Torrent Download:
   ```python
   config.torrent_seed_ratio = 1.0
   await cli.download_file('magnet:?xt=urn:btih:...', Path('downloads'))
   ```

4. Batch Download with Progress:
   ```python
   with Progress() as progress:
       task_id = progress.add_task("Downloading...", total=len(urls))
       for url in urls:
           await cli.download_file(url, Path('downloads'))
           progress.advance(task_id)
   ```

Error Handling:
--------------
1. Network Errors:
   ```python
   try:
       await cli.download_file(url, path)
   except DownloadError as e:
       print(f"Download failed: {e}")
   ```

2. System Errors:
   ```python
   try:
       await cli.batch_download(urls, path)
   except Exception as e:
       print(f"System error: {e}")
   ```

Performance Tips:
---------------
1. Optimize for your system:
   ```python
   optimizer = DownloadOptimizer(config)
   config = optimizer.optimize_settings()
   ```

2. Use appropriate chunk sizes:
   ```python
   config.chunk_size = optimizer.get_optimal_chunk_size()
   ```

3. Monitor system resources:
   ```python
   with cli.monitor:
       await cli.download_file(url, path)
   print(cli.monitor.get_stats())
   ```
"""

if __name__ == "__main__":
    print("This is a configuration module. Run downloader.py instead.")

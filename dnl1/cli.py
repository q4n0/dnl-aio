# cli.py

import os
import sys
import asyncio
import argparse
import signal
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from core import DownloadConfig, AsyncDownloader, SystemInfo
from protocols import ProtocolManager, DownloadTracker, DownloadInfo

def print_banner():
    banner = """
\033[34m
    ▄▄▄▄    ▄██   ▄   ▄▄▄▄▄▓█████   ██████ ▓█████  ▄████▄  
   ▓█████▄  ░▒████▄   ▓  ██▒▓█   ▀ ▒██    ▒ ▓█   ▀ ▒██▀ ▀█  
   ▒██▒ ▄██ ░░▓█▄   █▒ ▓██░▒███   ░ ▓██▄   ▒███   ▒▓█    ▄ 
   ▒██░█▀    ░▒████▓ ░ ▓██░▒▓█  ▄   ▒   ██▒▒▓█  ▄ ▒▓▓▄ ▄██▒
   ░▓█  ▀█▓   ▒▒▓  ▒   ░██░░▒████▒▒██████▒▒░▒████▒▒ ▓███▀ ░
   ░▒▓███▀▒   ░ ▒  ▒   ░▓  ░░ ▒░ ░▒ ▒▓▒ ▒ ░░░ ▒░ ░░ ░▒ ▒  ░
   ▒░▒   ░    ░ ░  ░    ▒   ░ ░  ░░ ░▒  ░ ░ ░ ░  ░  ░  ▒   
    ░    ░      ░       ▒     ░   ░  ░  ░     ░   ░        
    ░         ░         ░     ░  ░      ░     ░  ░░ ░      
         ░                                         ░        
\033[0m
\033[36m╔════════════════════════════════════════════════════════════╗
║                Advanced Download Manager v1.0                 ║
║          Developed by: b0urn3 (https://github.com/q4n0)     ║
╚════════════════════════════════════════════════════════════╝\033[0m

\033[35m• GitHub:    github.com/q4n0
- Twitter:   @byt3s3c
- Instagram: @onlybyhive\033[0m
"""
    print(banner)
    
class PerformanceMonitor:
    """Monitor system and download performance"""
    
    def __init__(self):
        self.system_info = SystemInfo()
        self.start_time = datetime.now()
        self.download_speeds: List[float] = []
        self.cpu_usage: List[float] = []
        self.memory_usage: List[float] = []

    def update_metrics(self, current_speed: float):
        """Update performance metrics"""
        try:
            import psutil
            
            self.download_speeds.append(current_speed)
            self.cpu_usage.append(psutil.cpu_percent())
            self.memory_usage.append(psutil.virtual_memory().percent)
            
            # Keep only last 60 seconds of data
            if len(self.download_speeds) > 60:
                self.download_speeds.pop(0)
                self.cpu_usage.pop(0)
                self.memory_usage.pop(0)
        except ImportError:
            pass

    def get_average_speed(self) -> float:
        """Get average download speed"""
        if self.download_speeds:
            return sum(self.download_speeds) / len(self.download_speeds)
        return 0.0

    def get_stats(self) -> Dict[str, str]:
        """Get current performance statistics"""
        return {
            'avg_speed': f"{self.get_average_speed():.2f} MB/s",
            'cpu_usage': f"{sum(self.cpu_usage) / len(self.cpu_usage):.1f}%" if self.cpu_usage else "N/A",
            'memory_usage': f"{sum(self.memory_usage) / len(self.memory_usage):.1f}%" if self.memory_usage else "N/A",
            'duration': str(datetime.now() - self.start_time).split('.')[0]
        }

class DownloadCLI:
    """Command Line Interface for Download Manager"""
    
    def __init__(self):
        self.console = Console()
        self.config = DownloadConfig()
        self.protocol_manager = ProtocolManager(self.config)
        self.tracker = DownloadTracker()
        self.monitor = PerformanceMonitor()
        self.running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_interrupt)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, self.handle_interrupt)

    def handle_interrupt(self, signum, frame):
        """Handle interrupt signals"""
        self.running = False
        self.console.print("\n[yellow]Received interrupt signal. Cleaning up...[/yellow]")
        # Allow clean shutdown of active downloads
        asyncio.get_event_loop().stop()

    def create_layout(self) -> Layout:
        """Create rich layout for UI"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        return layout

    def create_header(self) -> Panel:
        """Create header panel"""
        return Panel(
            Text("Download Manager", style="bold magenta", justify="center"),
            style="cyan"
        )

    def create_footer(self, stats: Dict[str, str]) -> Panel:
        """Create footer panel with performance stats"""
        stats_text = Text()
        stats_text.append("Speed: ", style="dim")
        stats_text.append(stats['avg_speed'], style="cyan")
        stats_text.append(" | CPU: ", style="dim")
        stats_text.append(stats['cpu_usage'], style="green")
        stats_text.append(" | Memory: ", style="dim")
        stats_text.append(stats['memory_usage'], style="yellow")
        stats_text.append(" | Duration: ", style="dim")
        stats_text.append(stats['duration'], style="blue")
        
        return Panel(stats_text, style="cyan")

    def create_progress_table(self, downloads: List[DownloadInfo]) -> Table:
        """Create table with download progress"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File")
        table.add_column("Progress")
        table.add_column("Speed")
        table.add_column("Status")
        
        for download in downloads:
            table.add_row(
                Path(download.url).name,
                f"{download.progress:.1f}%",
                download.speed or "N/A",
                download.status
            )
        
        return table

    async def download_file(self, url: str, output_path: Path):
        """Download a file with progress tracking"""
        try:
            with Progress() as progress:
                download_info = await self.protocol_manager.download(
                    url,
                    output_path,
                    progress
                )
                self.tracker.add_download(download_info)
                return download_info
        except Exception as e:
            self.console.print(f"[red]Error downloading {url}: {str(e)}[/red]")
            return None

    async def batch_download(self, urls: List[str], output_path: Path):
        """Download multiple files concurrently"""
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.download_file(url, output_path))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, DownloadInfo)]

    def show_main_menu(self):
        """Show main menu options"""
        self.console.print("\n[bold magenta]Download Manager[/bold magenta]")
        self.console.print("[yellow]1. Download File[/yellow]")
        self.console.print("[yellow]2. Batch Download[/yellow]")
        self.console.print("[yellow]3. Show Active Downloads[/yellow]")
        self.console.print("[yellow]4. Show Download History[/yellow]")
        self.console.print("[yellow]5. Settings[/yellow]")
        self.console.print("[yellow]6. Exit[/yellow]")
        
        return Prompt.ask(
            "[cyan]Choose an option[/cyan]",
            choices=['1', '2', '3', '4', '5', '6']
        )

    async def handle_single_download(self):
        """Handle single file download"""
        url = Prompt.ask("Enter URL to download")
        output_path = Path(Prompt.ask(
            "Enter output path",
            default=str(Path.home() / 'Downloads')
        ))
        
        download_info = await self.download_file(url, output_path)
        if download_info and download_info.status == 'completed':
            self.console.print("[green]Download completed successfully![/green]")
        else:
            self.console.print("[red]Download failed.[/red]")

    async def handle_batch_download(self):
        """Handle batch download from file or URLs"""
        input_type = Prompt.ask(
            "Enter URLs from (file/manual)",
            choices=['file', 'manual']
        )
        
        urls = []
        if input_type == 'file':
            file_path = Prompt.ask("Enter path to file containing URLs")
            try:
                with open(file_path) as f:
                    urls = [line.strip() for line in f if line.strip()]
            except Exception as e:
                self.console.print(f"[red]Error reading file: {str(e)}[/red]")
                return
        else:
            while True:
                url = Prompt.ask("Enter URL (or empty to start downloading)")
                if not url:
                    break
                urls.append(url)
        
        if not urls:
            self.console.print("[yellow]No URLs to download[/yellow]")
            return
        
        output_path = Path(Prompt.ask(
            "Enter output directory",
            default=str(Path.home() / 'Downloads')
        ))
        
        self.console.print(f"[cyan]Starting batch download of {len(urls)} files...[/cyan]")
        results = await self.batch_download(urls, output_path)
        
        successful = len([r for r in results if r and r.status == 'completed'])
        self.console.print(f"[green]Successfully downloaded: {successful}/{len(urls)}[/green]")

    def show_active_downloads(self):
        """Show currently active downloads"""
        downloads = self.tracker.get_active_downloads()
        if not downloads:
            self.console.print("[yellow]No active downloads[/yellow]")
            return
        
        table = self.create_progress_table(downloads)
        self.console.print(table)

    def show_download_history(self):
        """Show download history"""
        history = self.tracker.get_download_history()
        if not history:
            self.console.print("[yellow]No download history available[/yellow]")
            return
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Started")
        table.add_column("Completed")
        
        for entry in history:
            table.add_row(
                Path(entry['url']).name,
                entry['file_type'],
                entry['status'],
                entry['started_at'],
                entry['completed_at'] or 'N/A'
            )
        
        self.console.print(table)

    def show_settings(self):
        """Show and modify settings"""
        self.console.print("\n[bold]Current Settings:[/bold]")
        self.console.print(f"Max concurrent downloads: {self.config.max_concurrent_downloads}")
        self.console.print(f"Connections per file: {self.config.max_connections_per_file}")
        self.console.print(f"Chunk size: {self.config.chunk_size / 1024 / 1024}MB")
        
        if Confirm.ask("Would you like to modify settings?"):
            self.config.max_concurrent_downloads = int(Prompt.ask(
                "Enter max concurrent downloads",
                default=str(self.config.max_concurrent_downloads)
            ))
            self.config.max_connections_per_file = int(Prompt.ask(
                "Enter connections per file",
                default=str(self.config.max_connections_per_file)
            ))
            chunk_size_mb = int(Prompt.ask(
                "Enter chunk size (MB)",
                default=str(self.config.chunk_size / 1024 / 1024)
            ))
            self.config.chunk_size = chunk_size_mb * 1024 * 1024

    async def run(self):
        """Main CLI loop"""
        self.console.print("[bold cyan]Starting Download Manager...[/bold cyan]")
        
        while self.running:
            choice = self.show_main_menu()
            
            try:
                if choice == '1':
                    await self.handle_single_download()
                elif choice == '2':
                    await self.handle_batch_download()
                elif choice == '3':
                    self.show_active_downloads()
                elif choice == '4':
                    self.show_download_history()
                elif choice == '5':
                    self.show_settings()
                elif choice == '6':
                    self.running = False
                    break
                
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
                continue

def main():
    """Entry point"""
    cli = DownloadCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        cli.console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        cli.console.print(f"[red]Fatal error: {str(e)}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    main()

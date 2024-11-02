# Troubleshooting Guide: ModuleNotFoundError: No module named 'libtorrent'

## Quick Fix (Debian/Ubuntu/BlackArch)
```bash
# Install all required dependencies in one command
sudo nala install \
    python3-libtorrent \
    python3-dev \
    python3-pip \
    libboost-python-dev \
    libboost-dev \
    libboost-system-dev \
    libssl-dev \
    libffi-dev \
    aria2 \
    ffmpeg
```

## Step-by-Step Resolution

1. If you see the error:
```
ModuleNotFoundError: No module named 'libtorrent'
```

2. First try the simple fix:
```bash
sudo apt install python3-libtorrent
```

3. If that doesn't work, install the complete dependency set:
```bash
sudo nala install \
    python3-libtorrent \
    python3-dev \
    python3-pip \
    libboost-python-dev \
    libboost-dev \
    libboost-system-dev
```

## Verification
After installation, you can verify it's working by:
1. Running the downloader: `sudo python3 cli.py`
2. You should see the menu:
```
Starting Download Manager...

Download Manager
1. Download File
2. Batch Download
3. Show Active Downloads
4. Show Download History
5. Settings
6. Exit
```

## Common Issues and Solutions

1. **If packages are already installed:**
   - This is normal, the system will skip already installed packages
   - Continue with the installation as it will install missing dependencies

2. **If using pip instead of system packages:**
```bash
# Remove existing installations first
sudo apt remove python3-libtorrent
pip uninstall python-libtorrent

# Then install through pip
pip install python-libtorrent
```

3. **If permission errors occur:**
   - Always run with sudo when installing system packages
   - Example: `sudo nala install` or `sudo apt install`

## System-Specific Notes

For Debian/Ubuntu/BlackArch:
- Use `nala` if available (better interface than apt)
- All dependencies are available in standard repositories
- No need for manual compilation
- Package version 2.0.8-1+b1 is known to work correctly

## Additional Tips

1. If space is a concern:
   - The complete installation requires about 10.1 MB
   - Optional documentation can be skipped (saves ~7.4 MB)

2. Dependencies explained:
   - `python3-libtorrent`: Main torrent library
   - `libboost-python-dev`: Required for Python bindings
   - `libboost-dev`: Required boost libraries
   - `python3-dev`: Python development files
   - `libssl-dev`: Required for secure connections
   - `libffi-dev`: Foreign function interface library
   - `aria2`: For enhanced download capabilities
   - `ffmpeg`: For media processing support

3. After installation:
   - No system reboot required
   - Program can be run immediately
   - All features should be available

## If Problems Persist

1. Check Python version:
```bash
python3 --version
```

2. Verify libtorrent installation:
```bash
python3 -c "import libtorrent; print(libtorrent.__version__)"
```

3. Check system architecture:
```bash
uname -m
```

4. Contact support with:
   - Error messages
   - System information

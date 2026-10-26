import os
import sys
import urllib.request
import zipfile
from pathlib import Path

# Direct zip of OpenJDK 17 from GitHub Adoptium releases
jdk_url = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%2B7/OpenJDK17U-jdk_x64_windows_hotspot_17.0.12_7.zip"
temp_zip = Path(os.environ["TEMP"]) / "openjdk17.zip"
target_dir = Path(os.environ["LOCALAPPDATA"]) / "jdk-17"

print(f"Downloading OpenJDK 17 from {jdk_url}...")
req = urllib.request.Request(jdk_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
with urllib.request.urlopen(req) as resp, open(temp_zip, "wb") as f:
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    while True:
        chunk = resp.read(1024 * 1024)
        if not chunk:
            break
        f.write(chunk)
        downloaded += len(chunk)
        if total:
            pct = downloaded * 100 // total
            print(f"\rDownloading: {downloaded // (1024*1024)}MB / {total // (1024*1024)}MB ({pct}%)", end="", flush=True)

print(f"\nDownloaded to {temp_zip} ({temp_zip.stat().st_size} bytes)")

target_dir.mkdir(parents=True, exist_ok=True)
print(f"Extracting to {target_dir}...")
with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
    zip_ref.extractall(target_dir)

print("JDK 17 setup complete!")

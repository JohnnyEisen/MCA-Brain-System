import os
import zipfile
from pathlib import Path
from typing import List, Optional

# Configuration
VERSION = "v1.0.0"
GITHUB_LIMIT_BYTES = int(1.9 * 1024 * 1024 * 1024)
BUFFER_SIZE = 1024 * 1024

def compress_directory(source_path: Path, output_path: Path, exclude_names: Optional[List[str]] = None) -> None:
    """
    Compresses a directory into a zip file, excluding specified folder names.
    """
    if exclude_names is None:
        exclude_names = []
    
    print(f"-> Compressing: {output_path.name}...")
    
    # Ensure parent dir exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                # Filter directories in-place to prevent walking into them
                dirs[:] = [d for d in dirs if d not in exclude_names]
                
                for file in files:
                    file_path = Path(root) / file
                    # Create relative archive path
                    arcname = file_path.relative_to(source_path.parent)
                    zipf.write(file_path, arcname)
        print(f"   Done. Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
        
    except Exception as e:
        print(f"[!] Error compressing {source_path}: {e}")
        if output_path.exists():
            output_path.unlink()
        raise

def split_large_file(file_path: Path, chunk_size: int = GITHUB_LIMIT_BYTES) -> None:
    """
    Splits a file into strictly sized chunks if it exceeds the limit.
    Generated files: filename.zip.001, filename.zip.002, etc.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return
    
    file_size = file_path.stat().st_size
    if file_size <= chunk_size:
        return

    print(f"-> Large file detected ({file_size / (1024**3):.2f} GB). Splitting...")
    
    chunk_index = 1
    
    try:
        with open(file_path, 'rb') as src_f:
            while True:
                # Read strictly chunk_size bytes
                chunk_data = src_f.read(chunk_size)
                if not chunk_data:
                    break
                
                # Format: .001, .002, ...
                part_name = f"{file_path.name}.{chunk_index:03d}"
                part_path = file_path.parent / part_name
                
                with open(part_path, 'wb') as dst_f:
                    dst_f.write(chunk_data)
                
                print(f"   Created part: {part_name}")
                chunk_index += 1
        
        print(f"   Splitting complete. Removing original: {file_path.name}")
        file_path.unlink()
        
    except IOError as e:
        print(f"[!] Disk I/O error during splitting: {e}")
        raise

def main():
    root_dir = Path(__file__).resolve().parent.parent
    dist_dir = root_dir / "dist" / "MCA_Brain_System_v1.0"
    release_dir = root_dir / "releases"
    
    if not dist_dir.exists():
        print(f"[!] Build artifact missing at: {dist_dir}")
        print("    Run 'pack.bat' first to build the executable.")
        return

    print(f"=== Release Packaging Tool ({VERSION}) ===")
    print(f"Source: {dist_dir}")
    print(f"Output: {release_dir}\n")

    release_dir.mkdir(exist_ok=True)
    
    # Clean previous split artifacts to avoid mixing versions
    for artifact in release_dir.glob("*_FULL.zip.*"):
        artifact.unlink()

    # 1. Package LITE version (Code + Config, no heavyweight Libs)
    # Useful for users who already have dependencies or for patch updates.
    lite_zip = release_dir / f"MCA_Brain_System_{VERSION}_LITE.zip"
    if not lite_zip.exists():
        compress_directory(dist_dir, lite_zip, exclude_names=['lib'])
    else:
        print(f"-> LITE version already exists. Skipping.")

    # 2. Package FULL version
    full_zip = release_dir / f"MCA_Brain_System_{VERSION}_FULL.zip"
    if full_zip.exists():
        full_zip.unlink() 
        
    compress_directory(dist_dir, full_zip)
    
    # 3. Handle GitHub Size Limits
    split_large_file(full_zip)
    
    print("\n=== Summary ===")
    print(f"Location: {release_dir}")
    item_count = 0
    for item in release_dir.iterdir():
        if item.is_file():
            print(f"- {item.name:<40} | {item.stat().st_size / (1024*1024):>8.2f} MB")
            item_count += 1

if __name__ == "__main__":
    main()

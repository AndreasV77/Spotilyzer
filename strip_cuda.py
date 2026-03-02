"""
strip_cuda.py — Entfernt unnötige CUDA-DLLs und .lib-Dateien aus dem Build.

Spart ~1.56 GB an Dateigröße bei einem PyInstaller --onedir Build.

Nur die für MERT-Inferenz benötigten CUDA-Dateien werden behalten:
- cublas64_*.dll          (Matrix-Operationen, benötigt von PyTorch)
- cublasLt64_*.dll        (cuBLAS Light, benötigt)
- cudart64_*.dll          (CUDA Runtime)
- cudnn*.dll              (cuDNN, benötigt für Transformer-Inferenz)
- nvrtc*.dll              (CUDA Runtime Compiler, benötigt von Transformers)
- nvinfer*.dll            (TensorRT, optional aber klein)

Entfernt werden:
- Alle .lib Dateien (nur für Development/Linking, ~770 MB)
- cufft64_*.dll           (Fast Fourier Transform, ~278 MB)
- cusolver64_*.dll        (Linear Solver, ~184 MB)
- cusolverMg64_*.dll      (Multi-GPU Solver)
- cusparse64_*.dll        (Sparse Matrix, ~263 MB)
- curand64_*.dll          (Random Numbers, ~60 MB)
- cupti64_*.dll           (Profiling, ~4 MB)
- nvJitLink*.dll          (JIT Linker)

Usage:
    python strip_cuda.py                         # Standard: dist/Spotilyzer
    python strip_cuda.py --dist-dir dist/MyApp   # Eigener Pfad
    python strip_cuda.py --dry-run               # Nur anzeigen, nicht löschen
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


# DLL-Prefixes die ENTFERNT werden sollen
REMOVE_PREFIXES = [
    "cufft64",
    "cufftw64",
    "cusolver64",
    "cusolverMg64",
    "cusparse64",
    "curand64",
    "cupti64",
    "nvJitLink",
]

# Dateiendungen die entfernt werden sollen
REMOVE_EXTENSIONS = {
    ".lib",      # Development-only Linker-Dateien
}


def find_removable_files(dist_dir: Path) -> list[Path]:
    """Findet alle entfernbaren Dateien im Build-Verzeichnis."""
    removable: list[Path] = []

    for root, dirs, files in os.walk(dist_dir):
        root_path = Path(root)
        for filename in files:
            filepath = root_path / filename

            # .lib Dateien (Development-only)
            if filepath.suffix.lower() in REMOVE_EXTENSIONS:
                removable.append(filepath)
                continue

            # Unnötige CUDA-DLLs
            name_lower = filename.lower()
            if name_lower.endswith(".dll"):
                for prefix in REMOVE_PREFIXES:
                    if name_lower.startswith(prefix.lower()):
                        removable.append(filepath)
                        break

    return sorted(removable)


def format_size(size_bytes: int) -> str:
    """Formatiert Bytes als menschenlesbare Größe."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def main():
    parser = argparse.ArgumentParser(
        description="Entfernt unnötige CUDA-DLLs aus dem PyInstaller-Build."
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist/Spotilyzer"),
        help="Pfad zum Build-Verzeichnis (default: dist/Spotilyzer)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, nicht löschen",
    )
    args = parser.parse_args()

    dist_dir = args.dist_dir
    if not dist_dir.exists():
        print(f"FEHLER: Verzeichnis nicht gefunden: {dist_dir}")
        print("Erst PyInstaller-Build ausführen!")
        sys.exit(1)

    print(f"Scanne: {dist_dir.resolve()}")
    print()

    removable = find_removable_files(dist_dir)

    if not removable:
        print("Keine entfernbaren Dateien gefunden.")
        return

    total_size = 0
    libs_size = 0
    dlls_size = 0

    print(f"{'Datei':<60} {'Größe':>12}")
    print("-" * 74)

    for filepath in removable:
        size = filepath.stat().st_size
        total_size += size
        rel_path = filepath.relative_to(dist_dir)

        if filepath.suffix.lower() == ".lib":
            libs_size += size
        else:
            dlls_size += size

        marker = "[DRY RUN] " if args.dry_run else ""
        print(f"{marker}{str(rel_path):<58} {format_size(size):>12}")

    print("-" * 74)
    print(f"{'Gesamt':<60} {format_size(total_size):>12}")
    print(f"  davon .lib: {format_size(libs_size)}")
    print(f"  davon .dll: {format_size(dlls_size)}")
    print()

    if args.dry_run:
        print(f"[DRY RUN] {len(removable)} Dateien würden gelöscht werden.")
        print(f"[DRY RUN] Einsparung: {format_size(total_size)}")
        return

    # Bestätigung
    print(f"{len(removable)} Dateien werden gelöscht ({format_size(total_size)})...")

    deleted = 0
    for filepath in removable:
        try:
            filepath.unlink()
            deleted += 1
        except OSError as e:
            print(f"  WARNUNG: Konnte nicht löschen: {filepath} ({e})")

    print(f"\n{deleted}/{len(removable)} Dateien gelöscht.")
    print(f"Eingespart: {format_size(total_size)}")


if __name__ == "__main__":
    main()

# -*- mode: python ; coding: utf-8 -*-
"""
Spotilyzer — PyInstaller Spec-Datei.

Build:
    pyinstaller spotilyzer.spec

Ergebnis:
    dist/Spotilyzer/          ← Portable App-Ordner
    dist/Spotilyzer/main.exe  ← Entry Point

Hinweise:
- MERT-Modell wird NICHT gebundelt (~380 MB) → First-Run-Download via HuggingFace.
- CUDA-DLLs werden zunächst alle eingebunden;
  `strip_cuda.py` entfernt danach die unnötigen (~1.56 GB Einsparung).
- Das trainierte XGBoost-Modell wird gebundelt (models/spotilyzer_model.joblib).
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Pfade ──────────────────────────────────────────────────────────────
project_root = Path(SPECPATH)
main_script = str(project_root / "main.py")

# ── Daten-Dateien ──────────────────────────────────────────────────────
datas = [
    # Trainiertes XGBoost-Modell
    (str(project_root / "models" / "spotilyzer_model.joblib"), "models"),
]

# Training-Report (falls vorhanden)
training_report = project_root / "models" / "training_report.json"
if training_report.exists():
    datas.append((str(training_report), "models"))

# App-Icon (falls vorhanden)
icon_path = project_root / "resources" / "spotilyzer.ico"
if icon_path.exists():
    datas.append((str(icon_path), "resources"))

# Transformers-Config (für MERT-Cache-Erkennung)
datas += collect_data_files("transformers", include_py_files=False)

# ── Hidden Imports ─────────────────────────────────────────────────────
hiddenimports = [
    # XGBoost + sklearn
    "xgboost",
    "sklearn.utils._typedefs",
    "sklearn.utils._heap",
    "sklearn.utils._sorting",
    "sklearn.utils._vector_sentinel",
    "sklearn.preprocessing._label",
    # PySide6
    "PySide6.QtWidgets",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtMultimedia",
    # Torch/Torchaudio
    "torch",
    "torchaudio",
    "torchaudio.lib",
    # Transformers (für MERT)
    "transformers",
    "transformers.models.hubert",
]

# Alle torchaudio-Submodule einschließen
hiddenimports += collect_submodules("torchaudio")

# ── Ausschlüsse ────────────────────────────────────────────────────────
excludes = [
    # Alt-GUI (nicht mehr benötigt)
    "tkinter",
    "tkinterdnd2",
    "_tkinter",
    # Nicht benötigte Pakete
    "matplotlib",
    "IPython",
    "notebook",
    "jupyter",
    "scipy.spatial.cKDTree",
    # Multi-GPU (nicht nötig für Inferenz)
    "torch.distributed",
    "torch.testing",
    # Training-only
    "pandas",
    "tqdm",
]

# ── Analysis ───────────────────────────────────────────────────────────
a = Analysis(
    [main_script],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ (Python-Bytecode-Archiv) ──────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Spotilyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX verursacht Probleme mit CUDA-DLLs
    console=False,  # GUI-Modus (kein Konsolenfenster)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

# ── COLLECT (--onedir Modus) ──────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Spotilyzer",
)

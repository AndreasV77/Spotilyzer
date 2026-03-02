"""
spotilyzer_gui.py
=================
GUI mit Drag & Drop für Spotilyzer.

Features:
- Drag & Drop Zone für Audio-Dateien
- Analyse per Klick
- Ergebnis-Anzeige mit Konfidenz-Balken
- Batch-Support (mehrere Dateien)
- Highscore-Liste mit Sortierung
- Auto-Save (JSON) + manueller Export (CSV)

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import sys
import json
import csv
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

import numpy as np
import torch
import torchaudio
import joblib
from transformers import AutoModel, AutoProcessor

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

MODEL_PATH = Path("models/spotilyzer_model.joblib")
MERT_MODEL = "m-a-p/MERT-v1-95M"
TARGET_SAMPLE_RATE = 24000
MAX_AUDIO_LENGTH_SEC = 30

# Persistenz
AUTO_SAVE_PATH = Path("spotilyzer_results.json")
DEFAULT_EXPORT_NAME = "spotilyzer_export.csv"

SUPPORTED_FORMATS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac"}

# Farben
COLORS = {
    "hit": "#22c55e",      # Grün
    "mid": "#eab308",      # Gelb
    "flop": "#ef4444",     # Rot
    "bg": "#1e1e2e",       # Dunkler Hintergrund
    "fg": "#cdd6f4",       # Heller Text
    "accent": "#89b4fa",   # Akzent
    "dropzone": "#313244", # Dropzone Hintergrund
    "card": "#45475a",     # Karten-Hintergrund
    "btn": "#585b70",      # Button normal
    "btn_hover": "#6c7086",# Button hover
}

MEDALS = {0: "🥇", 1: "🥈", 2: "🥉"}


# ══════════════════════════════════════════════════════════════════════════════
# MERT EMBEDDER
# ══════════════════════════════════════════════════════════════════════════════

class MERTEmbedder:
    _instance = None
    
    def __init__(self, device: str = None, progress_callback=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.progress_callback = progress_callback
        
        if progress_callback:
            progress_callback("Lade MERT-Modell...")
        
        self.processor = AutoProcessor.from_pretrained(MERT_MODEL, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(MERT_MODEL, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()
    
    @classmethod
    def get_instance(cls, device=None, progress_callback=None):
        if cls._instance is None:
            cls._instance = cls(device, progress_callback)
        return cls._instance
    
    def load_audio(self, filepath: Path) -> torch.Tensor | None:
        try:
            waveform, sample_rate = torchaudio.load(filepath)
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            if sample_rate != TARGET_SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)
                waveform = resampler(waveform)
            max_samples = TARGET_SAMPLE_RATE * MAX_AUDIO_LENGTH_SEC
            if waveform.shape[1] > max_samples:
                start = (waveform.shape[1] - max_samples) // 2
                waveform = waveform[:, start:start + max_samples]
            return waveform.squeeze(0)
        except Exception as e:
            return None
    
    @torch.no_grad()
    def extract_embedding(self, waveform: torch.Tensor) -> np.ndarray | None:
        try:
            inputs = self.processor(
                waveform.numpy(),
                sampling_rate=TARGET_SAMPLE_RATE,
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs, output_hidden_states=True)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze(0)
            return embedding.cpu().numpy()
        except:
            return None
    
    def process_file(self, filepath: Path) -> np.ndarray | None:
        waveform = self.load_audio(filepath)
        if waveform is None:
            return None
        return self.extract_embedding(waveform)


# ══════════════════════════════════════════════════════════════════════════════
# GUI
# ══════════════════════════════════════════════════════════════════════════════

class SpotilyzerGUI:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Spotilyzer")
        self.root.geometry("650x800")
        self.root.configure(bg=COLORS["bg"])
        
        # State
        self.model_data = None
        self.embedder = None
        self.is_loading = False
        self.pending_files = []
        self.results = []  # Liste aller Ergebnisse
        self.sort_mode = "score"  # score, time, name
        
        self.setup_ui()
        self.load_saved_results()
        self.load_model_async()
    
    def setup_ui(self):
        # Titel
        title = tk.Label(
            self.root,
            text="🎵 SPOTILYZER",
            font=("Segoe UI", 24, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"]
        )
        title.pack(pady=(20, 5))
        
        subtitle = tk.Label(
            self.root,
            text="Hit/Mid/Flop Analyzer",
            font=("Segoe UI", 11),
            bg=COLORS["bg"],
            fg=COLORS["accent"]
        )
        subtitle.pack(pady=(0, 15))
        
        # Status-Label
        self.status_var = tk.StringVar(value="Initialisiere...")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg=COLORS["bg"],
            fg=COLORS["fg"]
        )
        self.status_label.pack(pady=(0, 10))
        
        # Drop Zone
        self.dropzone = tk.Frame(
            self.root,
            bg=COLORS["dropzone"],
            highlightbackground=COLORS["accent"],
            highlightthickness=2,
            width=550,
            height=120
        )
        self.dropzone.pack(pady=10, padx=50, fill="x")
        self.dropzone.pack_propagate(False)
        
        self.drop_label = tk.Label(
            self.dropzone,
            text="📂 Audio-Dateien hierher ziehen\noder klicken zum Auswählen",
            font=("Segoe UI", 11),
            bg=COLORS["dropzone"],
            fg=COLORS["fg"],
            justify="center"
        )
        self.drop_label.pack(expand=True)
        
        # Drag & Drop registrieren
        self.dropzone.drop_target_register(DND_FILES)
        self.dropzone.dnd_bind("<<Drop>>", self.on_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self.on_drop)
        
        # Klick zum Öffnen
        self.dropzone.bind("<Button-1>", self.on_click_browse)
        self.drop_label.bind("<Button-1>", self.on_click_browse)
        
        # ── Toolbar: Sortierung + Buttons ──
        toolbar = tk.Frame(self.root, bg=COLORS["bg"])
        toolbar.pack(fill="x", padx=20, pady=(15, 5))
        
        # Sortier-Label
        tk.Label(
            toolbar,
            text="Sortierung:",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["fg"]
        ).pack(side="left")
        
        # Sortier-Buttons
        self.sort_buttons = {}
        for mode, (text, icon) in [
            ("score", ("Hit-Score", "🏆")),
            ("time", ("Zuletzt", "🕐")),
            ("name", ("Name", "📝"))
        ]:
            btn = tk.Button(
                toolbar,
                text=f"{icon} {text}",
                font=("Segoe UI", 9),
                bg=COLORS["btn"],
                fg=COLORS["fg"],
                activebackground=COLORS["btn_hover"],
                activeforeground=COLORS["fg"],
                relief="flat",
                padx=8,
                pady=2,
                command=lambda m=mode: self.set_sort_mode(m)
            )
            btn.pack(side="left", padx=3)
            self.sort_buttons[mode] = btn
        
        # Spacer
        tk.Frame(toolbar, bg=COLORS["bg"]).pack(side="left", expand=True)
        
        # Export-Button
        export_btn = tk.Button(
            toolbar,
            text="📥 Export CSV",
            font=("Segoe UI", 9),
            bg=COLORS["btn"],
            fg=COLORS["fg"],
            activebackground=COLORS["btn_hover"],
            activeforeground=COLORS["fg"],
            relief="flat",
            padx=8,
            pady=2,
            command=self.export_csv
        )
        export_btn.pack(side="right", padx=3)
        
        # Clear-Button
        clear_btn = tk.Button(
            toolbar,
            text="🗑️ Clear",
            font=("Segoe UI", 9),
            bg=COLORS["btn"],
            fg=COLORS["fg"],
            activebackground=COLORS["btn_hover"],
            activeforeground=COLORS["fg"],
            relief="flat",
            padx=8,
            pady=2,
            command=self.clear_results
        )
        clear_btn.pack(side="right", padx=3)
        
        # Aktiven Sortier-Button markieren
        self.update_sort_button_style()
        
        # ── Stats-Leiste ──
        self.stats_frame = tk.Frame(self.root, bg=COLORS["dropzone"], padx=10, pady=8)
        self.stats_frame.pack(fill="x", padx=20, pady=(5, 10))
        
        self.stats_var = tk.StringVar(value="Keine Ergebnisse")
        self.stats_label = tk.Label(
            self.stats_frame,
            textvariable=self.stats_var,
            font=("Segoe UI", 10),
            bg=COLORS["dropzone"],
            fg=COLORS["fg"],
            anchor="w"
        )
        self.stats_label.pack(fill="x")
        
        # ── Ergebnis-Bereich ──
        self.results_frame = tk.Frame(self.root, bg=COLORS["bg"])
        self.results_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Scrollable Results
        self.canvas = tk.Canvas(self.results_frame, bg=COLORS["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Canvas-Breite anpassen
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        
        # ── Footer ──
        footer = tk.Frame(self.root, bg=COLORS["bg"])
        footer.pack(fill="x", pady=10)
        
        device = "GPU 🚀" if torch.cuda.is_available() else "CPU"
        device_label = tk.Label(
            footer,
            text=f"Device: {device}",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#6c7086"
        )
        device_label.pack(side="left", padx=20)
        
        self.autosave_label = tk.Label(
            footer,
            text=f"Auto-Save: {AUTO_SAVE_PATH.name}",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#6c7086"
        )
        self.autosave_label.pack(side="right", padx=20)
    
    def on_canvas_configure(self, event):
        """Passt die Breite des scrollable_frame an die Canvas-Breite an."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    # ══════════════════════════════════════════════════════════════════════════
    # PERSISTENZ
    # ══════════════════════════════════════════════════════════════════════════
    
    def load_saved_results(self):
        """Lädt gespeicherte Ergebnisse aus JSON."""
        if AUTO_SAVE_PATH.exists():
            try:
                with open(AUTO_SAVE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = data.get("results", [])
                    self.update_status(f"📂 {len(self.results)} gespeicherte Ergebnisse geladen")
            except Exception as e:
                self.results = []
    
    def save_results(self):
        """Speichert alle Ergebnisse in JSON (Auto-Save)."""
        try:
            data = {
                "version": "1.0",
                "updated": datetime.now().isoformat(),
                "count": len(self.results),
                "results": self.results
            }
            with open(AUTO_SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Auto-Save Fehler: {e}")
    
    def export_csv(self):
        """Exportiert aktuelle Ergebnisse als CSV."""
        if not self.results:
            messagebox.showinfo("Export", "Keine Ergebnisse zum Exportieren.")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV-Dateien", "*.csv")],
            initialfile=DEFAULT_EXPORT_NAME
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Datei", "Pfad", "Rating", "Hit%", "Mid%", "Flop%", 
                    "Konfidenz", "Analysiert"
                ])
                
                for r in self.get_sorted_results():
                    if "error" in r:
                        continue
                    probs = r.get("probabilities", {})
                    writer.writerow([
                        r.get("file", ""),
                        r.get("path", ""),
                        r.get("rating", "").upper(),
                        f"{probs.get('hit', 0):.1%}",
                        f"{probs.get('mid', 0):.1%}",
                        f"{probs.get('flop', 0):.1%}",
                        f"{r.get('confidence', 0):.1%}",
                        r.get("timestamp", "")
                    ])
            
            self.update_status(f"✅ Exportiert: {Path(filepath).name}")
        except Exception as e:
            messagebox.showerror("Export-Fehler", str(e))
    
    # ══════════════════════════════════════════════════════════════════════════
    # SORTIERUNG & DARSTELLUNG
    # ══════════════════════════════════════════════════════════════════════════
    
    def set_sort_mode(self, mode: str):
        """Setzt den Sortier-Modus und aktualisiert die Anzeige."""
        self.sort_mode = mode
        self.update_sort_button_style()
        self.refresh_results_display()
    
    def update_sort_button_style(self):
        """Markiert den aktiven Sortier-Button."""
        for mode, btn in self.sort_buttons.items():
            if mode == self.sort_mode:
                btn.configure(bg=COLORS["accent"], fg="#1e1e2e")
            else:
                btn.configure(bg=COLORS["btn"], fg=COLORS["fg"])
    
    def get_sorted_results(self) -> list:
        """Gibt Ergebnisse sortiert zurück."""
        valid = [r for r in self.results if "error" not in r]
        
        if self.sort_mode == "score":
            return sorted(valid, key=lambda r: r.get("probabilities", {}).get("hit", 0), reverse=True)
        elif self.sort_mode == "time":
            return sorted(valid, key=lambda r: r.get("timestamp", ""), reverse=True)
        elif self.sort_mode == "name":
            return sorted(valid, key=lambda r: r.get("file", "").lower())
        return valid
    
    def clear_results(self):
        """Löscht alle Ergebnisse nach Bestätigung."""
        if not self.results:
            return
        
        if messagebox.askyesno("Clear", f"{len(self.results)} Ergebnisse löschen?"):
            self.results = []
            self.save_results()
            self.refresh_results_display()
            self.update_stats()
            self.update_status("🗑️ Ergebnisse gelöscht")
    
    def update_stats(self):
        """Aktualisiert die Stats-Leiste."""
        if not self.results:
            self.stats_var.set("Keine Ergebnisse")
            return
        
        valid = [r for r in self.results if "error" not in r]
        if not valid:
            self.stats_var.set("Keine gültigen Ergebnisse")
            return
        
        hits = sum(1 for r in valid if r.get("rating") == "hit")
        mids = sum(1 for r in valid if r.get("rating") == "mid")
        flops = sum(1 for r in valid if r.get("rating") == "flop")
        
        # Best Track
        best = max(valid, key=lambda r: r.get("probabilities", {}).get("hit", 0))
        best_score = best.get("probabilities", {}).get("hit", 0)
        best_name = best.get("file", "?")[:25]
        
        self.stats_var.set(
            f"📊 {len(valid)} Tracks: {hits}🔥 {mids}➖ {flops}💀  │  "
            f"🏆 Best: {best_name} ({best_score:.0%})"
        )
    
    def refresh_results_display(self):
        """Aktualisiert die komplette Ergebnis-Anzeige."""
        # Alte Karten entfernen
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Neu aufbauen
        sorted_results = self.get_sorted_results()
        for idx, result in enumerate(sorted_results):
            self.create_result_card(result, rank=idx)
        
        self.update_stats()
    
    # ══════════════════════════════════════════════════════════════════════════
    # MODELL-LADEN
    # ══════════════════════════════════════════════════════════════════════════
    
    def load_model_async(self):
        """Lädt Modell und MERT im Hintergrund."""
        def load():
            self.is_loading = True
            try:
                # Modell laden
                self.update_status("Lade Spotilyzer-Modell...")
                if not MODEL_PATH.exists():
                    self.update_status("❌ Modell nicht gefunden! Erst train_model.py ausführen.")
                    return
                self.model_data = joblib.load(MODEL_PATH)
                
                # MERT laden
                self.update_status("Lade MERT (kann beim ersten Mal dauern)...")
                self.embedder = MERTEmbedder.get_instance(progress_callback=self.update_status)
                
                self.update_status("✅ Bereit – Dateien hierher ziehen!")
                self.is_loading = False
                
                # Gespeicherte Ergebnisse anzeigen
                if self.results:
                    self.root.after(100, self.refresh_results_display)
                
                # Falls Dateien während des Ladens gedroppt wurden
                if self.pending_files:
                    self.root.after(200, lambda: self.analyze_files(self.pending_files))
                    self.pending_files = []
                    
            except Exception as e:
                self.update_status(f"❌ Fehler: {str(e)[:50]}")
        
        threading.Thread(target=load, daemon=True).start()
    
    def update_status(self, text):
        """Thread-safe Status-Update."""
        self.root.after(0, lambda: self.status_var.set(text))
    
    # ══════════════════════════════════════════════════════════════════════════
    # DRAG & DROP / BROWSE
    # ══════════════════════════════════════════════════════════════════════════
    
    def on_drop(self, event):
        """Handler für Drag & Drop."""
        files_str = event.data
        if files_str.startswith("{"):
            files = self.root.tk.splitlist(files_str)
        else:
            files = files_str.split()
        
        valid_files = []
        for f in files:
            path = Path(f)
            if path.suffix.lower() in SUPPORTED_FORMATS:
                valid_files.append(path)
        
        if valid_files:
            if self.is_loading:
                self.pending_files.extend(valid_files)
                self.update_status(f"⏳ {len(self.pending_files)} Datei(en) warten auf Modell...")
            else:
                self.analyze_files(valid_files)
    
    def on_click_browse(self, event):
        """Öffnet Datei-Dialog."""
        if self.is_loading:
            return
        
        filetypes = [
            ("Audio-Dateien", "*.mp3 *.flac *.wav *.ogg *.m4a"),
            ("Alle Dateien", "*.*")
        ]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        if files:
            self.analyze_files([Path(f) for f in files])
    
    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSE
    # ══════════════════════════════════════════════════════════════════════════
    
    def analyze_files(self, files: list[Path]):
        """Analysiert eine Liste von Dateien."""
        def analyze():
            for filepath in files:
                # Duplikat-Check (gleicher Pfad)
                existing = next(
                    (r for r in self.results if r.get("path") == str(filepath)), 
                    None
                )
                if existing:
                    self.update_status(f"⏭️ Übersprungen (bereits analysiert): {filepath.name[:35]}")
                    continue
                
                self.update_status(f"🔄 Analysiere: {filepath.name[:40]}...")
                result = self.analyze_single(filepath)
                
                # Zur Liste hinzufügen
                self.results.append(result)
                
                # Auto-Save
                self.save_results()
                
                # UI aktualisieren
                self.root.after(0, self.refresh_results_display)
            
            self.update_status(f"✅ {len(files)} Datei(en) verarbeitet")
        
        threading.Thread(target=analyze, daemon=True).start()
    
    def analyze_single(self, filepath: Path) -> dict:
        """Analysiert eine einzelne Datei."""
        timestamp = datetime.now().isoformat()
        
        try:
            embedding = self.embedder.process_file(filepath)
            if embedding is None:
                return {
                    "file": filepath.name,
                    "path": str(filepath),
                    "timestamp": timestamp,
                    "error": "Konnte Audio nicht laden"
                }
            
            model = self.model_data["model"]
            label_encoder = self.model_data["label_encoder"]
            
            embedding_2d = embedding.reshape(1, -1)
            proba = model.predict_proba(embedding_2d)[0]
            pred_idx = np.argmax(proba)
            pred_label = label_encoder.inverse_transform([pred_idx])[0]
            
            prob_dict = {
                label: float(proba[i])
                for i, label in enumerate(label_encoder.classes_)
            }
            
            return {
                "file": filepath.name,
                "path": str(filepath),
                "timestamp": timestamp,
                "rating": pred_label,
                "confidence": float(proba[pred_idx]),
                "probabilities": prob_dict
            }
        except Exception as e:
            return {
                "file": filepath.name,
                "path": str(filepath),
                "timestamp": timestamp,
                "error": str(e)
            }
    
    # ══════════════════════════════════════════════════════════════════════════
    # ERGEBNIS-KARTEN
    # ══════════════════════════════════════════════════════════════════════════
    
    def create_result_card(self, result: dict, rank: int = 0):
        """Erstellt eine Ergebnis-Karte."""
        card = tk.Frame(
            self.scrollable_frame,
            bg=COLORS["card"],
            padx=15,
            pady=10
        )
        card.pack(fill="x", pady=4, padx=5)
        
        if "error" in result:
            # Fehler-Karte
            tk.Label(
                card,
                text=f"❌ {result['file']}",
                font=("Segoe UI", 10, "bold"),
                bg=COLORS["card"],
                fg="#f38ba8",
                anchor="w"
            ).pack(fill="x")
            tk.Label(
                card,
                text=result["error"],
                font=("Segoe UI", 9),
                bg=COLORS["card"],
                fg=COLORS["fg"],
                anchor="w"
            ).pack(fill="x")
            return
        
        rating = result["rating"]
        conf = result["confidence"]
        probs = result["probabilities"]
        hit_pct = probs.get("hit", 0)
        
        emoji = {"hit": "🔥", "mid": "➖", "flop": "💀"}[rating]
        color = COLORS[rating]
        medal = MEDALS.get(rank, "")
        
        # Header: Rang + Dateiname + Rating
        header = tk.Frame(card, bg=COLORS["card"])
        header.pack(fill="x")
        
        # Medaille/Rang
        rank_text = medal if medal else f"#{rank + 1}"
        tk.Label(
            header,
            text=rank_text,
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["card"],
            fg=COLORS["accent"] if medal else "#6c7086",
            width=4,
            anchor="w"
        ).pack(side="left")
        
        # Dateiname
        tk.Label(
            header,
            text=result["file"][:40],
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["card"],
            fg=COLORS["fg"],
            anchor="w"
        ).pack(side="left", fill="x", expand=True)
        
        # Rating + Score
        tk.Label(
            header,
            text=f"{emoji} {rating.upper()} ({hit_pct:.0%})",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["card"],
            fg=color,
            anchor="e"
        ).pack(side="right")
        
        # Konfidenz-Balken
        bar_frame = tk.Frame(card, bg=COLORS["card"])
        bar_frame.pack(fill="x", pady=(8, 5))
        
        for label in ["hit", "mid", "flop"]:
            pct = probs.get(label, 0)
            lbl_emoji = {"hit": "🔥", "mid": "➖", "flop": "💀"}[label]
            
            row = tk.Frame(bar_frame, bg=COLORS["card"])
            row.pack(fill="x", pady=1)
            
            tk.Label(
                row,
                text=f"{lbl_emoji}",
                font=("Segoe UI", 9),
                bg=COLORS["card"],
                fg=COLORS["fg"],
                width=3
            ).pack(side="left")
            
            # Bar container
            bar_bg = tk.Frame(row, bg="#313244", height=12)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(5, 10))
            bar_bg.pack_propagate(False)
            
            # Filled portion
            bar_fill = tk.Frame(bar_bg, bg=COLORS[label], height=12)
            bar_fill.place(relwidth=pct, relheight=1)
            
            tk.Label(
                row,
                text=f"{pct:.0%}",
                font=("Segoe UI", 9),
                bg=COLORS["card"],
                fg=COLORS["fg"],
                width=5
            ).pack(side="right")
    
    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        print("Fehler: tkinterdnd2 nicht installiert!")
        print("Installieren mit: pip install tkinterdnd2")
        sys.exit(1)
    
    app = SpotilyzerGUI()
    app.run()


if __name__ == "__main__":
    main()

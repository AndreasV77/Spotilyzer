"""English UI strings for Spotilyzer.

This is the canonical reference locale.  Every key used in the codebase
should have an entry here.  Keys follow the pattern ``<module>.<element>``
(e.g. ``toolbar.open``, ``dialog.clear.title``).

Pluralization: use separate ``.singular`` / ``.plural`` keys rather than
inline suffix placeholders so that non-English locales can provide their
own forms without needing to match English morphology.

Note: the GUI currently uses hardcoded strings.  This file is the first
step toward full localization — wiring the GUI to call ``t()`` is a
separate refactoring task.
"""

STRINGS: dict[str, str] = {
    # ── App / Window ─────────────────────────────────────────────\n    "app.title":                       "Spotilyzer v{version}",
    "app.about.title":                 "About Spotilyzer",
    "app.about.body":                  (
        "Spotilyzer v{version}\n\n"
        "Hit/Mid/Flop Analyzer\n"
        "Evaluates the mainstream compatibility of audio tracks.\n\n"
        "ML pipeline: MERT-v1-95M + XGBoost\n"
        "Device: {device}{model_info}\n\n"
        "GUI: PySide6 (Qt 6)\n"
        "Theme: Buena Vista-inspired"
    ),

    # ── Toolbar ───────────────────────────────────────────────\n    "toolbar.name":                    "Tools",
    "toolbar.open":                    "Open",
    "toolbar.open.tooltip":            "Select audio files to analyze",
    "toolbar.export":                  "Export",
    "toolbar.export.tooltip":          "Export results",
    "toolbar.clear":                   "Clear",
    "toolbar.clear.tooltip":           "Delete all results",
    "toolbar.mode.simple":             "Simple",
    "toolbar.mode.simple.tooltip":     "Simple view — rating + results only",
    "toolbar.mode.balanced":           "Balanced",
    "toolbar.mode.balanced.tooltip":   "Balanced view — rating + audio info",
    "toolbar.mode.pro":                "Pro",
    "toolbar.mode.pro.tooltip":        "Pro view — all fields + dock panels",

    # ── Menu bar ──────────────────────────────────────────────\n    "menu.file":                       "&File",
    "menu.file.quit":                  "&Quit",
    "menu.view":                       "&View",
    "menu.help":                       "&Help",
    "menu.help.about":                 "About Spotilyzer",

    # ── Status bar ────────────────────────────────────────────\n    "statusbar.device":                "Device: {device} | Model: {model}",
    "statusbar.device.loading":        "Device: ...",

    # ── Pipeline status messages ────────────────────────────\n    "status.init":                     "Initializing ML pipeline...",
    "status.ready":                    "✅ Ready! Device: {device} | Drop audio files here or click to select",
    "status.model_missing":            (
        "❌ Model not found! "
        "Please provide a 'spotilyzer_model_*.joblib' in models/ "
        "or set a path under Settings > Model."
    ),
    "status.device_changed":           "Device changed to '{device}' — reloading pipeline...",
    "status.model_changed":            "Model changed ({label}) — reloading pipeline...",
    "status.model_auto":               "Auto-detect",
    "status.analyzed":                 "✅ {count} tracks analyzed | {hits} hits found",
    "status.error":                    "Error: {msg}",
    "status.export_saved":             "✅ Export saved: {path}",
    "status.cleared":                  "Results cleared",

    # ── Pipeline error dialog ────────────────────────────────\n    "dialog.pipeline_error.title":     "Pipeline Error",
    "dialog.pipeline_error.body":      "The ML pipeline could not be initialized:\n\n{error}",

    # ── Not-ready / busy dialogs ────────────────────────────\n    "dialog.not_ready.title":          "Not Ready",
    "dialog.not_ready.body":           "The ML pipeline is still initializing.\nPlease wait a moment.",
    "dialog.busy.title":               "Analysis Running",
    "dialog.busy.body":                "An analysis is already in progress.\nPlease wait for it to complete.",

    # ── File dialog ────────────────────────────────────────────\n    "dialog.open_files.title":         "Select Audio Files",
    "dialog.open_files.filter":        "Audio Files ({ext});;All Files (*.*)",

    # ── Export dialog ───────────────────────────────────────────\n    "dialog.export.title":             "Export Results",
    "dialog.export.no_results.title":  "Nothing to Export",
    "dialog.export.no_results.body":   "No results to export.",
    "dialog.export_error.title":       "Export Error",
    "dialog.export_error.body":        "Error while exporting:\n{error}",

    # ── Clear dialog ────────────────────────────────────────────\n    "dialog.clear.title":              "Delete Results?",
    "dialog.clear.body":               "{count} results will be deleted.\nContinue?",

    # ── Central widget ──────────────────────────────────────────\n    "central.title":                   "SPOTILYZER",
    "central.subtitle":                "Hit/Mid/Flop Analyzer",
    "central.status.init":             "Initializing...",
    "central.stats.empty":             "No results",
    "central.stats.summary":           "{count} Tracks: {hits} Hit  {mids} Mid  {flops} Flop  │  Best: {best} ({score})",
    "central.sort.label":              "Sort:",
    "central.sort.score":              "Hit Score",
    "central.sort.time":               "Recent",
    "central.sort.name":               "Name",
    "central.dropzone.more":           "+ Drop more files or click",
    "central.dropzone.empty":          "Drop audio files here\nor click to select",

    # ── Drop zone ──────────────────────────────────────────────\n    "dropzone.instructions":           "Drop audio files here\nor click to select",
    "dropzone.loading":                "Loading model...",

    # ── File panel ──────────────────────────────────────────────\n    "panel.files.title":               "Files",
    "panel.files.nav.up":              "Go up one folder",
    "panel.files.nav.home":            "Home directory",
    "panel.files.path.placeholder":    "Folder path...",
    "panel.files.analyze_btn":         "▶  Analyze selection",
    "panel.files.analyze_btn.n.singular": "▶  Analyze {count} file",
    "panel.files.analyze_btn.n.plural":   "▶  Analyze {count} files",
    "panel.files.status":              "{count} audio files in this folder",
    "panel.files.status.ready":        "Ready",

    # ── Highscore panel ───────────────────────────────────────────\n    "panel.highscore.title":           "Highscore",
    "panel.highscore.ranking":         "Ranking",
    "panel.highscore.no_results":      "No results",
    "panel.highscore.count.singular":  "{count} track",
    "panel.highscore.count.plural":    "{count} tracks",
    "panel.highscore.col.rank":        "#",
    "panel.highscore.col.file":        "File",
    "panel.highscore.col.rating":      "Rating",
    "panel.highscore.col.hit_pct":     "Hit%",
    "panel.highscore.col.mid_pct":     "Mid%",
    "panel.highscore.col.flop_pct":    "Flop%",
    "panel.highscore.col.confidence":  "Confidence",

    # ── History panel ─────────────────────────────────────────────\n    "panel.history.title":             "History",
    "panel.history.no_results":        "0 entries",
    "panel.history.count.singular":    "{count} entry",
    "panel.history.count.plural":      "{count} entries",
    "panel.history.export_label":      "Export:",
    "panel.history.export.json":       "JSON",
    "panel.history.export.json.tip":   "Export as JSON (re-importable)",
    "panel.history.export.csv":        "CSV",
    "panel.history.export.csv.tip":    "Export as CSV (Excel-compatible)",
    "panel.history.export.md":         "MD",
    "panel.history.export.md.tip":     "Export as Markdown",
    "panel.history.export.txt":        "TXT",
    "panel.history.export.txt.tip":    "Export as plain text",
    "panel.history.dialog.title":      "Export Results as {fmt}",
    "panel.history.dialog.filter.json": "JSON file (*.json)",
    "panel.history.dialog.filter.csv": "CSV file (*.csv)",
    "panel.history.dialog.filter.md":  "Markdown file (*.md)",
    "panel.history.dialog.filter.txt": "Text file (*.txt)",
    "panel.history.export_ok.title":   "Export Successful",
    "panel.history.export_ok.body":    "Results saved:\n{path}",
    "panel.history.export_err.title":  "Export Error",
    "panel.history.export_err.body":   "Error while exporting:\n{error}",

    # ── Tech panel ───────────────────────────────────────────────\n    "panel.tech.title":                "Technical",
    "panel.tech.no_track":             "No track selected",
    "panel.tech.field.duration":       "Duration",
    "panel.tech.field.format":         "Format",
    "panel.tech.field.sample_rate":    "Sample Rate",
    "panel.tech.field.channels":       "Channels",
    "panel.tech.field.bitrate":        "Bitrate",
    "panel.tech.field.file_size":      "File Size",
    "panel.tech.field.bpm":            "BPM",
    "panel.tech.field.lufs":           "LUFS",
    "panel.tech.field.key":            "Key",
    "panel.tech.field.centroid":       "Centroid",
    "panel.tech.field.flatness":       "Flatness",
    "panel.tech.field.onset_rate":     "Onset Rate",
    "panel.tech.waveform.title":       "Waveform",
    "panel.tech.player.play":          "▶  Play",
    "panel.tech.player.pause":         "⏸  Pause",
    "panel.tech.player.stop":          "■  Stop",
    "panel.tech.player.time":          "0:00 / 0:00",
    "panel.tech.rating_line":          "{rating} | Hit: {hit_pct} | Confidence: {conf_pct}",

    # ── Settings panel ───────────────────────────────────────────\n    "panel.settings.title":            "Settings",
    "panel.settings.group.view":       "View",
    "panel.settings.view.mode_label":  "Mode:",
    "panel.settings.view.mode_hint":   "Simple = rating only | Balanced = + audio info | Pro = everything",
    "panel.settings.group.theme":      "Theme",
    "panel.settings.theme.mode_label": "Mode:",
    "panel.settings.theme.dark":       "Dark",
    "panel.settings.theme.light":      "Light",
    "panel.settings.theme.accent_label": "Accent:",
    "panel.settings.theme.accent_pick.tooltip": "Pick accent color",
    "panel.settings.theme.accent_pick.title":   "Choose Accent Color",
    "panel.settings.theme.accent_reset":         "Reset",
    "panel.settings.theme.accent_reset.tooltip": "Reset accent color to default",
    "panel.settings.group.system":     "System",
    "panel.settings.device.label":     "Device:",
    "panel.settings.device.auto":      "Auto (prefer CUDA)",
    "panel.settings.device.cuda":      "GPU (CUDA)",
    "panel.settings.device.cpu":       "CPU",
    "panel.settings.device.tooltip":   "Change takes effect after pipeline restart",
    "panel.settings.device.active_label": "Active:",
    "panel.settings.device.loaded_label": "Loaded:",
    "panel.settings.model.label":      "Model:",
    "panel.settings.model.placeholder": "Auto-detect...",
    "panel.settings.model.tooltip":    "Custom model (.joblib)\nEmpty = auto-detect (newest spotilyzer_model_*.joblib in models/)",
    "panel.settings.model.browse":     "Browse...",
    "panel.settings.model.auto":       "Auto",
    "panel.settings.model.auto.tooltip": "Reset to automatic model detection",
    "panel.settings.model.dialog.title": "Select Spotilyzer Model",
    "panel.settings.model.dialog.filter": "Joblib model (*.joblib);;All Files (*)",
    "panel.settings.group.export":     "Export Defaults",
    "panel.settings.export.json":      "JSON (structured, re-importable)",
    "panel.settings.export.csv":       "CSV (Excel/Sheets-compatible)",
    "panel.settings.export.md":        "Markdown (formatted report)",
    "panel.settings.export.txt":       "TXT (plain text)",
    "panel.settings.group.files":      "Files",
    "panel.settings.files.home_label": "Start folder:",
    "panel.settings.files.home_placeholder": "Use last folder...",
    "panel.settings.files.browse":     "Browse...",
    "panel.settings.files.reset":      "Reset",
    "panel.settings.files.hint":       "Empty = open last used folder",
    "panel.settings.files.dialog.title": "Select Start Folder",
    "panel.settings.group.clap":       "CLAP Genre/Mood",
    "panel.settings.clap.checkbox":    "Include genre and mood tags",
    "panel.settings.clap.hint":        (
        "Zero-shot classification via LAION CLAP.\n"
        "~776 MB download on first launch.\n"
        "Slows analysis by ~2–5 s/track."
    ),
    "panel.settings.clap.vram_label":  "VRAM mode:",
    "panel.settings.clap.sequential":  "Sequential (≤ 6 GB VRAM)",
    "panel.settings.clap.concurrent":  "Concurrent (> 6 GB VRAM)",
}

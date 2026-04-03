"""
AudioInfo-Extraktion - Technische Metadaten aus Audio-Dateien.

Extrahiert: Duration, Sample-Rate, Channels, Bitrate, Format, Dateigröße,
BPM (Tempo), LUFS (Lautheit), Key (Tonart),
Spectral Centroid (Hz), Spectral Flatness (0-1), Onset Rate (onsets/s).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torchaudio

from spotilyzer.core._audio_loader import load_audio_file
from spotilyzer.data.models import AudioInfo


def extract_audio_info(filepath: Path) -> AudioInfo:
    """
    Extrahiert alle technischen Metadaten aus einer Audio-Datei.

    Args:
        filepath: Pfad zur Audio-Datei.

    Returns:
        AudioInfo-Dataclass mit allen verfügbaren Feldern.
    """
    path = Path(filepath)

    # Basis-Info via soundfile.info() (schnell, kein torchcodec nötig)
    try:
        import soundfile as sf
        info = sf.info(str(path))
        duration_sec = info.duration
        sample_rate = info.samplerate
        channels = info.channels
        # Bitrate aus Dateigröße und Dauer schätzen (soundfile liefert kein bitrate)
        if duration_sec > 0:
            bitrate = int(path.stat().st_size * 8 / duration_sec / 1000)
        else:
            bitrate = None
    except Exception:
        duration_sec = 0.0
        sample_rate = 0
        channels = 0
        bitrate = None

    # Datei-Metadaten
    file_size_bytes = path.stat().st_size if path.exists() else 0
    audio_format = path.suffix.lstrip(".").lower()

    # Audio laden für berechnete Metriken
    bpm = None
    lufs = None
    true_peak_dbfs = None
    key = None
    spectral_centroid = None
    spectral_flatness = None
    onset_rate = None

    try:
        waveform, sr = load_audio_file(path)

        # Mono für Analyse
        if waveform.shape[0] > 1:
            waveform_mono = waveform.mean(dim=0, keepdim=True)
        else:
            waveform_mono = waveform

        # BPM-Schätzung (librosa Dynamic Programming)
        bpm = _estimate_bpm(waveform_mono.squeeze(0), sr)

        # LUFS (EBU R128 via pyloudnorm)
        lufs = _estimate_lufs(waveform, sr)

        # True Peak (EBU R128: 4× Oversampling nach ITU-R BS.1770)
        # PLR = true_peak_dbfs - lufs  (berechnet bei Ausgabe)
        true_peak_dbfs = _estimate_true_peak(waveform)

        # Key-Erkennung (Chroma-basiert)
        key = _estimate_key(waveform_mono.squeeze(0), sr)

        # Spektrale Features: Centroid, Flatness, Onset Rate
        spectral_centroid, spectral_flatness, onset_rate = _estimate_spectral_features(
            waveform_mono.squeeze(0), sr
        )

    except Exception:
        pass  # Berechnete Metriken bleiben None

    return AudioInfo(
        duration_sec=duration_sec,
        sample_rate=sample_rate,
        channels=channels,
        bitrate=bitrate,
        format=audio_format,
        file_size_bytes=file_size_bytes,
        bpm=bpm,
        lufs=lufs,
        true_peak_dbfs=true_peak_dbfs,
        key=key,
        spectral_centroid=spectral_centroid,
        spectral_flatness=spectral_flatness,
        onset_rate=onset_rate,
    )


def _estimate_bpm(waveform: torch.Tensor, sample_rate: int) -> Optional[float]:
    """
    Schätzt BPM via librosa Beat-Tracking (Dynamic Programming).

    Algorithmus:
    1. Audio auf 22050 Hz resamplen (librosa-Standard)
    2. Onset-Envelope berechnen
    3. Dynamisches Programmier-Beat-Tracking (librosa.beat.beat_track)
    4. Globale Tempo-Schätzung via Tempo-Periodogramm (librosa.feature.tempo)
    5. Oktavfehler-Korrektur: präferiert 70-180 BPM
    """
    try:
        import librosa

        audio = waveform.numpy().astype(np.float32)

        # Auf 22050 Hz resamplen (librosa-Standard, schnellere Verarbeitung)
        target_sr = 22050
        if sample_rate != target_sr:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)

        # Onset-Envelope einmal berechnen — für beide Methoden wiederverwendet
        onset_env = librosa.onset.onset_strength(y=audio, sr=target_sr)

        # Methode 1: Dynamic Programming Beat Tracker
        tempo_dp, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=target_sr)
        tempo_dp = float(np.atleast_1d(tempo_dp)[0])

        # Methode 2: Globale Tempo-Schätzung via Periodogramm
        tempo_global = librosa.feature.tempo(onset_envelope=onset_env, sr=target_sr)
        tempo_global = float(np.atleast_1d(tempo_global)[0])

        # Oktavfehler-Korrektur: präferiere 70-180 BPM
        def _correct_octave(t: float) -> float:
            if t > 180 and 70 <= t / 2 <= 180:
                return t / 2
            if t < 70 and 70 <= t * 2 <= 180:
                return t * 2
            return t

        tempo_dp = _correct_octave(tempo_dp)
        tempo_global = _correct_octave(tempo_global)

        # Konsens: wenn beide Methoden nah beieinander liegen → Mittelwert
        # Sonst: Dynamic Programming bevorzugen (stabiler bei variabler Rhythmik)
        if abs(tempo_dp - tempo_global) < 5.0:
            bpm = (tempo_dp + tempo_global) / 2
        else:
            bpm = tempo_dp

        if 40 <= bpm <= 240:
            return round(bpm, 1)

        return None
    except Exception:
        return None


def _estimate_lufs(waveform: torch.Tensor, sample_rate: int) -> Optional[float]:
    """
    Misst Integrated LUFS nach EBU R128 via pyloudnorm.

    Volle Implementierung: K-Weighting + 400ms-Block-Gating.
    Fallback auf RMS-Approximation falls pyloudnorm nicht verfügbar.
    """
    try:
        import pyloudnorm as pyln

        # pyloudnorm erwartet numpy float64, shape: (samples,) oder (samples, channels)
        data = waveform.numpy().astype(np.float64)
        if data.ndim == 1:
            data = data[:, np.newaxis]  # (samples, 1)
        else:
            data = data.T  # (samples, channels) — waveform ist (channels, samples)

        meter = pyln.Meter(sample_rate)  # EBU R128
        lufs = meter.integrated_loudness(data)

        # pyloudnorm gibt -inf für Stille zurück
        if not np.isfinite(lufs):
            return -70.0

        return round(float(lufs), 1)
    except Exception:
        # Fallback: RMS → dBFS
        try:
            rms = float(torch.sqrt(torch.mean(waveform ** 2)))
            if rms < 1e-10:
                return -70.0
            lufs = max(20 * math.log10(rms), -70.0)
            return round(lufs, 1)
        except Exception:
            return None


def _estimate_true_peak(waveform: torch.Tensor) -> Optional[float]:
    """
    Misst True Peak nach EBU R128 / ITU-R BS.1770 via 4× Oversampling.

    Das Sample-Maximum kann Inter-Sample-Peaks übersehen, die bei der
    DA-Wandlung über 0 dBFS steigen (Clipping im Player/Streaming-Encoder).
    4× Upsampling mit scipy.signal.resample_poly erkennt diese Peaks.

    Fallback auf Sample-Maximum wenn scipy nicht verfügbar.
    """
    try:
        from scipy.signal import resample_poly

        # (channels, samples) → numpy float64
        audio = waveform.numpy().astype(np.float64)

        # 4× Upsample (alle Kanäle gleichzeitig, axis=1)
        upsampled = resample_poly(audio, up=4, down=1, axis=1)

        peak = float(np.abs(upsampled).max())
        if peak < 1e-10:
            return None
        return round(20 * math.log10(peak), 1)

    except Exception:
        # Fallback: Sample-Peak (unterschätzt leicht bei Inter-Sample-Clipping)
        try:
            peak = float(waveform.abs().max())
            if peak < 1e-10:
                return None
            return round(20 * math.log10(peak), 1)
        except Exception:
            return None


def _estimate_key(waveform: torch.Tensor, sample_rate: int) -> Optional[str]:
    """
    Schätzt die Tonart via Chroma-CQT + Krumhansl-Schmuckler-Algorithmus.

    librosa.feature.chroma_cqt verwendet den Constant-Q-Transform:
    - Logarithmisch verteilte Frequenzbins = bessere Tonhöhen-Auflösung
    - Deutlich genauer bei Bassnoten als STFT-basierte Chroma
    - chroma_cens (Energy Normalized Statistics) als Fallback für robustere
      Tonart-Erkennung bei dynamischen Tracks
    """
    try:
        import librosa

        audio = waveform.numpy().astype(np.float32)

        target_sr = 22050
        if sample_rate != target_sr:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)

        # Chroma CQT — bessere Frequenzauflösung als STFT-Chroma
        # chroma_cens glättet über Zeit und normalisiert Energie → robuster
        chroma_cqt = librosa.feature.chroma_cqt(y=audio, sr=target_sr, bins_per_octave=36)
        chroma_cens = librosa.feature.chroma_cens(y=audio, sr=target_sr)

        # Zeitliches Mittel beider Chroma-Versionen, dann kombinieren
        chroma_mean_cqt  = np.mean(chroma_cqt, axis=1)
        chroma_mean_cens = np.mean(chroma_cens, axis=1)

        if chroma_mean_cqt.sum() < 1e-10:
            return None

        # Gewichtetes Mittel (CENS robuster bei Rauschen)
        chroma = 0.5 * (chroma_mean_cqt / (chroma_mean_cqt.sum() + 1e-10)
                        + chroma_mean_cens / (chroma_mean_cens.sum() + 1e-10))

        # Krumhansl-Kessler Profile (unverändert)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        note_names = ["C", "C#", "D", "D#", "E", "F",
                      "F#", "G", "G#", "A", "A#", "B"]

        best_corr = -1.0
        best_key = "C major"

        for shift in range(12):
            rotated_major = np.roll(major_profile, shift)
            rotated_minor = np.roll(minor_profile, shift)

            corr_major = float(np.corrcoef(chroma, rotated_major)[0, 1])
            corr_minor = float(np.corrcoef(chroma, rotated_minor)[0, 1])

            if corr_major > best_corr:
                best_corr = corr_major
                best_key = f"{note_names[shift]} major"
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_key = f"{note_names[shift]} minor"

        return best_key
    except Exception:
        return None


def _estimate_spectral_features(
    waveform: torch.Tensor, sample_rate: int
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Berechnet Spectral Centroid, Spectral Flatness und Onset Rate via librosa.

    Returns:
        (spectral_centroid_hz, spectral_flatness, onset_rate_per_sec)

        spectral_centroid: Frequenz-Schwerpunkt des Spektrums in Hz.
            Niedrig (~1-2 kHz) = dunkler/bässiger Sound.
            Hoch (~4-6 kHz) = heller/luftiger Sound.

        spectral_flatness: Verhältnis geometrisches/arithmetisches Mittel der Spektrum-Leistung.
            0.0 = rein tonal (Sinus-ähnlich).
            1.0 = weißes Rauschen.
            Typische Musik: 0.05-0.4.

        onset_rate: Anzahl erkannter Onsets (Transienten) pro Sekunde.
            Niedrig (~1-3/s) = sparse, ambient.
            Hoch (~8-15/s) = dicht, rythmisch komplex.
    """
    try:
        import librosa

        audio = waveform.numpy().astype(np.float32)

        target_sr = 22050
        if sample_rate != target_sr:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)

        duration = len(audio) / target_sr
        if duration < 0.1:
            return None, None, None

        # Spectral Centroid (Hz) — Schwerpunkt der Frequenzenergie
        centroid = librosa.feature.spectral_centroid(y=audio, sr=target_sr)
        spectral_centroid = float(np.mean(centroid))

        # Spectral Flatness (0=tonal, 1=rauschartig)
        flatness = librosa.feature.spectral_flatness(y=audio)
        spectral_flatness = float(np.mean(flatness))

        # Onset Rate — Transienten pro Sekunde
        onsets = librosa.onset.onset_detect(y=audio, sr=target_sr, units="time")
        onset_rate = len(onsets) / duration

        return (
            round(spectral_centroid, 1),
            round(spectral_flatness, 4),
            round(onset_rate, 2),
        )
    except Exception:
        return None, None, None


def extract_waveform_display(
    filepath: Path,
    target_width: int = 800,
) -> Optional[np.ndarray]:
    """
    Extrahiert eine downgesampelte Waveform für die Visualisierung.

    Args:
        filepath: Pfad zur Audio-Datei.
        target_width: Anzahl Datenpunkte (Pixel-Breite).

    Returns:
        2D numpy Array [2, target_width] mit Min/Max pro Spalte,
        oder None bei Fehler.
    """
    try:
        waveform, sr = load_audio_file(filepath)

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0)
        else:
            waveform = waveform.squeeze(0)

        samples = waveform.numpy()
        n_samples = len(samples)

        if n_samples < target_width:
            target_width = n_samples

        chunk_size = n_samples // target_width
        if chunk_size < 1:
            return None

        # Reshape und Min/Max pro Chunk
        trimmed = samples[: chunk_size * target_width]
        chunks = trimmed.reshape(target_width, chunk_size)

        mins = chunks.min(axis=1)
        maxs = chunks.max(axis=1)

        return np.array([mins, maxs])
    except Exception:
        return None

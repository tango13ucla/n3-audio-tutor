#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kyoto Bedtime Story Soundscape & Mastering Engine (`sleep_soundscape.py`)

Turns a raw Gemini TTS Japanese bedtime voice stem (or local gentle fallback) into a
48kHz stereo Kyoto Ryokan lullaby production (~20 min):
  1. Ultra-warm damped Felt Piano lullaby (Fmaj9 / Dm9 / Bbmaj7 / C6/9, progressively slowing
     from 7.5s/chord in Act 1 to 12.0s/chord in Act 4, heavily low-passed at 2.4kHz for zero harshness)
  2. Parasympathetic 5.5-breath/min velvet low pad (11s gentle breathing swell)
  3. Three organic Kyoto night ambiences (`soft_rain`, `night_breeze`, `hearth_tea`, zero white-noise hiss)
  4. Studio vocal warmth chain (velvet de-ess >5.2kHz, intimate 200Hz warmth, subtle Kyoto wooden-room
     reverb, smooth sidechain music ducking, progressive -3.5dB sleep attenuation across Acts 1->4,
     and a 75-second cosine S-curve music fade to complete silence)
  5. Daily relay puller from `antigravity-workspace` (`ntfy.sh`) + persistent archive `audio/sleep/manifest.json`
     that NEVER deletes yesterday's unlistened stories (keeps rolling 28-night library).
"""
from __future__ import annotations

import argparse
import base64
import datetime
import gzip
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import wave
from typing import Any
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SLEEP_DIR = os.path.join(BASE_DIR, "audio", "sleep")
MANIFEST_PATH = os.path.join(SLEEP_DIR, "manifest.json")
PT_TZ = ZoneInfo("America/Los_Angeles")
DEFAULT_SLEEP_RELAY_TOPIC = "n3sleep_8c4e19b7a2d54f0391e6b4c8"
SR = 48000
MAX_ARCHIVED_EPISODES = 28


def _decode_audio_to_f32_mono(path: str, target_sr: int = SR) -> Any:
    """Decodes any WAV/MP3 cleanly to float32 mono at target_sr via ffmpeg."""
    import numpy as np
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp_wav = tf.name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", path, "-ac", "1", "-ar", str(target_sr),
                "-c:a", "pcm_s16le", tmp_wav,
            ],
            check=True,
        )
        with wave.open(tmp_wav, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


def _butter_lp(x: Any, cutoff_hz: float, sr: int = SR, order: int = 2) -> Any:
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    wn = min(0.95, max(0.001, cutoff_hz / (0.5 * sr)))
    sos = butter(order, wn, btype="low", output="sos")
    return sosfiltfilt(sos, x).astype(np.float32)


def _butter_hp(x: Any, cutoff_hz: float, sr: int = SR, order: int = 2) -> Any:
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    wn = min(0.95, max(0.001, cutoff_hz / (0.5 * sr)))
    sos = butter(order, wn, btype="high", output="sos")
    return sosfiltfilt(sos, x).astype(np.float32)


def _butter_bp(x: Any, low_hz: float, high_hz: float, sr: int = SR, order: int = 2) -> Any:
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    lo = min(0.92, max(0.0008, low_hz / (0.5 * sr)))
    hi = min(0.96, max(lo + 0.005, high_hz / (0.5 * sr)))
    sos = butter(order, [lo, hi], btype="band", output="sos")
    return sosfiltfilt(sos, x).astype(np.float32)


def _master_sleep_voice_stereo(voice_mono: Any, total_n: int) -> tuple[Any, Any]:
    """
    Studio bedtime vocal polish:
      - High-pass rumble clean (<65Hz)
      - Velvet proximity warmth (+2.2dB around 160-320Hz)
      - Gentle bedtime de-harsh / de-ess above 5.0kHz (-4dB) so sibilants never pierce sleepy ears
      - Intimate Kyoto tatami-room stereo ambience (10% wet, low-passed <2.1kHz)
      - Progressive sleep attenuation (-3.2dB across the 20-min arc)
    """
    import numpy as np
    v = np.zeros(total_n, dtype=np.float32)
    n = min(total_n, voice_mono.size)
    v[:n] = voice_mono[:n]

    # Clean sub-rumble
    v = _butter_hp(v, 65.0, SR, order=2)

    # Velvet warmth band + gentle de-harsh high-frequency smoothing
    warm_band = _butter_bp(v, 140.0, 360.0, SR, order=2)
    harsh_band = _butter_hp(v, 5000.0, SR, order=2)
    v = v + 0.24 * warm_band - 0.38 * harsh_band

    # Subtle gentle peak taming (zero jarring syllables)
    v = np.tanh(v * 1.18) / 1.18

    # Progressive gentle volume softening from start (1.00) -> deep sleep end (0.72)
    prog = np.linspace(0.0, 1.0, total_n, dtype=np.float32)
    sleep_curve = 1.0 - 0.28 * (prog ** 1.35)
    v *= sleep_curve

    # Intimate warm Kyoto wooden-room early reflections (very subtle, velvety)
    wet_src = _butter_lp(v, 2100.0, SR, order=2)
    rev_l = np.zeros(total_n, dtype=np.float32)
    rev_r = np.zeros(total_n, dtype=np.float32)
    taps_l = [(0.023, 0.055), (0.047, 0.040), (0.089, 0.026), (0.148, 0.016), (0.235, 0.009)]
    taps_r = [(0.029, 0.052), (0.056, 0.038), (0.103, 0.024), (0.167, 0.015), (0.262, 0.008)]
    for d_s, g in taps_l:
        d = int(d_s * SR)
        if d < total_n:
            rev_l[d:] += g * wet_src[:-d]
    for d_s, g in taps_r:
        d = int(d_s * SR)
        if d < total_n:
            rev_r[d:] += g * wet_src[:-d]

    out_l = v + rev_l
    out_r = v + rev_r
    return out_l, out_r


def _generate_felt_piano_lullaby(total_n: int, seed: int = 2026) -> tuple[Any, Any]:
    """
    48kHz stereo Ryuichi Sakamoto / Satie-inspired sparse solo wool-felt upright piano lullaby
    + feather-light warm harmonic breath cushion (ZERO heavy synth drone).
    Single tender notes spaced lazily apart, progressively slowing from Act 1 -> Act 4 in warm F major.
    """
    import numpy as np
    bed_l = np.zeros(total_n, dtype=np.float32)
    bed_r = np.zeros(total_n, dtype=np.float32)

    # Sparse single-note arpeggio voicings: (bass_root, warm_fifth, tender_top1, tender_top2)
    # Warm F major / D minor Kyoto lullaby palette
    voicings_a = [
        (174.61, 261.63, 329.63, 440.00),  # F3, C4, E4, A4 (Fmaj7)
        (146.83, 220.00, 293.66, 392.00),  # D3, A3, D4, G4 (Dm11)
        (116.54, 174.61, 261.63, 349.23),  # Bb2, F3, C4, F4 (Bbmaj9)
        (130.81, 196.00, 261.63, 329.63),  # C3, G3, C4, E4 (C)
    ]
    voicings_b = [
        (174.61, 261.63, 349.23, 392.00),  # F3, C4, F4, G4 (Fadd9)
        (164.81, 220.00, 261.63, 392.00),  # E3, A3, C4, G4 (Am7/E)
        (146.83, 220.00, 261.63, 349.23),  # D3, A3, C4, F4 (Dm7)
        (116.54, 174.61, 220.00, 293.66),  # Bb2, F3, A3, D4 (Bbmaj7)
        (130.81, 196.00, 293.66, 329.63),  # C3, G3, D4, E4 (Cadd9)
        (174.61, 220.00, 261.63, 329.63),  # F3, A3, C4, E4 (Fmaj7)
    ]
    # Ultra-sparse sleepy lullaby high melody droplets (F pentatonic)
    mel_phrases = [
        (523.25, 440.00),  # C5 -> A4
        (587.33, 523.25),  # D5 -> C5
        (440.00, 392.00),  # A4 -> G4
        (392.00, 349.23),  # G4 -> F4
        None,              # Breathing bar
    ]

    def _add_felt_key(start_s: float, freq: float, vel: float, decay_rate: float, pan: float) -> None:
        i0 = int(round(start_s * SR))
        note_dur = min(7.5, 4.2 / max(0.25, decay_rate))
        n = min(total_n - i0, int(round(note_dur * SR)))
        if i0 < 0 or n < 120:
            return
        nt = np.arange(n, dtype=np.float32) / float(SR)
        # Soft wool-felt hammer attack (24ms) + realistic string harmonic decay
        atk = np.minimum(1.0, nt / 0.024)
        # Slight natural piano unison warmth (+0.08% detuned second string)
        f2 = freq * 1.0007
        h1 = (0.62 * np.sin(2.0 * math.pi * freq * nt) + 0.38 * np.sin(2.0 * math.pi * f2 * nt)) * np.exp(-nt * decay_rate)
        h2 = 0.24 * np.sin(4.0 * math.pi * freq * nt) * np.exp(-nt * (decay_rate * 2.15))
        h3 = 0.08 * np.sin(6.0 * math.pi * freq * nt) * np.exp(-nt * (decay_rate * 3.6))
        h4 = 0.025 * np.sin(8.0 * math.pi * freq * nt) * np.exp(-nt * (decay_rate * 5.2))
        tail = np.minimum(1.0, (n - np.arange(n, dtype=np.float32)) / (0.25 * SR))
        sig = (h1 + h2 + h3 + h4) * atk * tail * vel
        gl = math.cos((pan + 1.0) * math.pi / 4.0)
        gr = math.sin((pan + 1.0) * math.pi / 4.0)
        bed_l[i0 : i0 + n] += sig * gl
        bed_r[i0 : i0 + n] += sig * gr

    cur_s = 0.25
    bar_idx = 0
    total_sec = total_n / float(SR)

    while cur_s < total_sec - 1.5:
        prog = cur_s / max(1.0, total_sec)
        if prog < 0.24:
            step_s = 1.48
            voicing = voicings_a[bar_idx % len(voicings_a)]
            vel_scale = 1.00
            play_mel = (bar_idx % 2 == 1)
        elif prog < 0.62:
            step_s = 1.68
            voicing = voicings_b[bar_idx % len(voicings_b)]
            vel_scale = 0.94
            play_mel = (bar_idx % 2 == 1)
        elif prog < 0.86:
            step_s = 2.05
            voicing = voicings_a[bar_idx % len(voicings_a)]
            vel_scale = 0.80
            play_mel = (bar_idx % 3 == 1)
        else:
            step_s = 2.55
            voicing = (174.61, 261.63, 329.63) if (bar_idx % 2 == 0) else (116.54, 174.61, 261.63)
            vel_scale = 0.66
            play_mel = False  # Pure floating cradling notes only in Act 4

        # Fingerpicked slow Satie-like broken arpeggio: one gentle key every 1.5s - 2.5s!
        for ki, f in enumerate(voicing):
            k_time = cur_s + ki * step_s
            if k_time >= total_sec - 1.0:
                break
            vel = (0.30 if ki == 0 else (0.20 if ki == 1 else 0.16)) * vel_scale
            pan = -0.34 + 0.68 * (ki / max(1, len(voicing) - 1))
            dec = 0.42 if ki == 0 else 0.56
            _add_felt_key(k_time, f, vel, dec, pan)

        # Optional whisper-soft high lullaby melody pair floating above
        if play_mel:
            phrase = mel_phrases[(bar_idx // 2 + seed) % len(mel_phrases)]
            if phrase:
                _add_felt_key(cur_s + step_s * 1.65, phrase[0], 0.13 * vel_scale, 0.62, 0.22)
                _add_felt_key(cur_s + step_s * 3.15, phrase[1], 0.11 * vel_scale, 0.58, 0.16)

        # Feather-light warm air cushion on the bass root (10x lighter than a synth organ!)
        pad_dur = step_s * (len(voicing) + 0.8)
        p0 = int(round(cur_s * SR))
        pn = min(total_n - p0, int(round(pad_dur * SR)))
        if pn > 400:
            pt = np.arange(pn, dtype=np.float32) / float(SR)
            p_env = np.sin(math.pi * pt / max(0.5, pad_dur)) ** 1.6
            p_sig = np.sin(2.0 * math.pi * voicing[0] * pt) * p_env * (0.042 * vel_scale)
            bed_l[p0 : p0 + pn] += p_sig * 0.72
            bed_r[p0 : p0 + pn] += p_sig * 0.70

        cur_s += step_s * (len(voicing) + 0.55)
        bar_idx += 1

    # Gentle felt-piano tonal warmth (3.4kHz low-pass keeps wood clarity while erasing any metallic edge)
    bed_l = _butter_lp(bed_l, 3400.0, SR, order=2)
    bed_r = _butter_lp(bed_r, 3400.0, SR, order=2)

    # Lush warm Kyoto wooden-hall reverb bloom (cross-coupled stereo tail)
    rev_l = np.zeros(total_n, dtype=np.float32)
    rev_r = np.zeros(total_n, dtype=np.float32)
    taps = [(0.059, 0.22), (0.127, 0.16), (0.233, 0.11), (0.379, 0.07), (0.587, 0.04)]
    for d_s, g in taps:
        d = int(d_s * SR)
        if d < total_n:
            rev_l[d:] += g * bed_r[:-d]
            rev_r[d:] += g * bed_l[:-d]
    rev_l = _butter_lp(rev_l, 2200.0, SR, order=2)
    rev_r = _butter_lp(rev_r, 2200.0, SR, order=2)
    bed_l += rev_l
    bed_r += rev_r

    rms = float(np.sqrt(np.mean(0.5 * (bed_l ** 2 + bed_r ** 2)) + 1e-12))
    if rms > 1e-5:
        bed_l *= 0.095 / rms
        bed_r *= 0.095 / rms
    return bed_l, bed_r


def _generate_night_ambience(total_n: int, ambience: str = "soft_rain", seed: int = 2026) -> tuple[Any, Any]:
    """
    Organic Kyoto night ambience bed (feather-light, zero tunnel drone, zero harsh hiss!):
      - `soft_rain`: Delicate misty rain outside Kyoto shoji eaves (260Hz-2.1kHz gentle pink curve)
      - `night_breeze`: Soft cedar-leaf night air (180Hz-820Hz)
      - `hearth_tea`: Cozy tatami room warmth + distant soft kettle whisper
    """
    import numpy as np
    rng = np.random.default_rng(seed + 77)
    w_l = rng.standard_normal(total_n).astype(np.float32)
    w_r = rng.standard_normal(total_n).astype(np.float32)
    t = np.arange(total_n, dtype=np.float32) / float(SR)

    if ambience == "night_breeze":
        amb_l = _butter_bp(w_l, 160.0, 740.0, SR, order=2)
        amb_r = _butter_bp(w_r, 160.0, 740.0, SR, order=2)
        swell_l = 0.68 + 0.32 * np.sin(2.0 * math.pi * 0.042 * t + 0.3) * np.cos(2.0 * math.pi * 0.017 * t)
        swell_r = 0.68 + 0.32 * np.sin(2.0 * math.pi * 0.039 * t + 1.4) * np.cos(2.0 * math.pi * 0.021 * t)
        amb_l *= swell_l
        amb_r *= swell_r
        target_rms = 0.011
    elif ambience == "hearth_tea":
        low_l = _butter_bp(w_l, 150.0, 480.0, SR, order=2)
        low_r = _butter_bp(w_r, 150.0, 480.0, SR, order=2)
        steam_l = _butter_bp(w_l, 620.0, 1650.0, SR, order=2) * 0.30
        steam_r = _butter_bp(w_r, 620.0, 1650.0, SR, order=2) * 0.30
        swell = 0.86 + 0.14 * np.sin(2.0 * math.pi * 0.06 * t)
        amb_l = (low_l + steam_l) * swell
        amb_r = (low_r + steam_r) * swell
        target_rms = 0.010
    else:
        # Feather-light misty Kyoto rain outside eaves (clean >260Hz so ZERO muddy rumble!)
        mist_l = _butter_bp(w_l, 280.0, 2100.0, SR, order=2)
        mist_r = _butter_bp(w_r, 280.0, 2100.0, SR, order=2)
        soft_l = _butter_bp(w_l, 200.0, 750.0, SR, order=2) * 0.45
        soft_r = _butter_bp(w_r, 200.0, 750.0, SR, order=2) * 0.45
        curtain_l = 0.84 + 0.16 * np.sin(2.0 * math.pi * 0.043 * t)
        curtain_r = 0.84 + 0.16 * np.sin(2.0 * math.pi * 0.040 * t + 1.1)
        amb_l = (mist_l + soft_l) * curtain_l
        amb_r = (mist_r + soft_r) * curtain_r
        c_l = 0.70 * amb_l + 0.30 * amb_r
        c_r = 0.70 * amb_r + 0.30 * amb_l
        amb_l, amb_r = c_l, c_r
        target_rms = 0.013

    rms = float(np.sqrt(np.mean(0.5 * (amb_l ** 2 + amb_r ** 2)) + 1e-12))
    if rms > 1e-6:
        amb_l *= target_rms / rms
        amb_r *= target_rms / rms
    return amb_l, amb_r


def master_bedtime_episode(
    voice_stem_path: str,
    meta: dict,
    out_mp3_path: str,
    bitrate: str = "80k",
) -> dict:
    """
    Masters a complete ~20-minute 48kHz stereo bedtime story MP3 combining:
      - Studio-polished Gemini TTS Japanese voice stem
      - Sparse Ryuichi Sakamoto / Satie solo wool-felt piano lullaby
      - Feather-light theme-matched Kyoto Night Ambience
      - Silky sidechain ducking + 75s cosine S-curve fade to silence
    """
    import numpy as np
    os.makedirs(os.path.dirname(out_mp3_path), exist_ok=True)
    voice_raw = _decode_audio_to_f32_mono(voice_stem_path, target_sr=SR)
    total_n = voice_raw.size
    total_sec = total_n / float(SR)
    seed = int(hashlib.sha256(str(meta.get("date") or "2026-11-27").encode()).hexdigest()[:8], 16) % 100000
    ambience = str(meta.get("ambience") or "soft_rain")
    outro_tail_s = float(meta.get("outro_tail_sec") or 75.0)

    print(f"[sleep-master] Mastering {meta.get('title_ja')} ({total_sec/60.0:.2f} min, ambience={ambience})...", flush=True)

    # 1. Master voice
    v_l, v_r = _master_sleep_voice_stereo(voice_raw, total_n)

    # 2. Compute smooth voice activity envelope for silky sidechain ducking
    hop = 960
    n_frames = int(math.ceil(total_n / float(hop)))
    v_abs = np.abs(voice_raw)
    pad_len = n_frames * hop - total_n
    if pad_len > 0:
        v_abs = np.pad(v_abs, (0, pad_len))
    frame_rms = np.sqrt(np.mean(v_abs.reshape(n_frames, hop) ** 2, axis=1) + 1e-12)
    speech_active = (frame_rms > 0.011).astype(np.float32)

    atk_a = 1.0 - math.exp(-1.0 / (0.38 * (SR / hop)))
    rel_a = 1.0 - math.exp(-1.0 / (1.15 * (SR / hop)))
    env_f = np.zeros(n_frames, dtype=np.float32)
    cur = 0.0
    for i in range(n_frames):
        tgt = float(speech_active[i])
        cur += (atk_a if tgt > cur else rel_a) * (tgt - cur)
        env_f[i] = cur
    x_f = np.linspace(0.0, total_n - 1, n_frames, dtype=np.float64)
    duck_env = np.interp(np.arange(total_n, dtype=np.float64), x_f, env_f).astype(np.float32)

    # Music blooms gently to 1.00 in intro/pauses/outro, softens to 0.56 under voice
    music_duck = 1.0 - 0.44 * duck_env

    # 3. Synthesize 48kHz stereo Sparse Solo Felt Piano + Feather-light Kyoto Ambience
    mus_l, mus_r = _generate_felt_piano_lullaby(total_n, seed=seed)
    amb_l, amb_r = _generate_night_ambience(total_n, ambience=ambience, seed=seed)

    # 4. Global Bedtime Fade-In (6.5s cosine S-curve) & Deep-Sleep Fade-Out
    t_all = np.arange(total_n, dtype=np.float32) / float(SR)
    intro_fade = np.clip(t_all / 6.5, 0.0, 1.0)
    intro_fade = 0.5 - 0.5 * np.cos(math.pi * intro_fade)

    prog = t_all / max(1.0, total_sec)
    music_arc = 1.0 - 0.24 * (prog ** 1.4)

    fade_start_m = max(0.0, total_sec - outro_tail_s * 0.92)
    fade_end_m = max(fade_start_m + 8.0, total_sec - 7.0)
    m_out = 1.0 - np.clip((t_all - fade_start_m) / (fade_end_m - fade_start_m), 0.0, 1.0)
    m_out = 0.5 - 0.5 * np.cos(math.pi * m_out)

    fade_start_a = max(0.0, total_sec - outro_tail_s * 0.72)
    fade_end_a = max(fade_start_a + 8.0, total_sec - 1.2)
    a_out = 1.0 - np.clip((t_all - fade_start_a) / (fade_end_a - fade_start_a), 0.0, 1.0)
    a_out = 0.5 - 0.5 * np.cos(math.pi * a_out)

    # Luxury Kyoto balance: Voice intimate front, Delicate solo felt piano floating beside her, Feather mist rain
    mix_l = v_l * 1.00 + mus_l * (0.28 * music_duck * music_arc * intro_fade * m_out) + amb_l * (0.85 * intro_fade * a_out)
    mix_r = v_r * 1.00 + mus_r * (0.28 * music_duck * music_arc * intro_fade * m_out) + amb_r * (0.85 * intro_fade * a_out)

    # Silky master limiter (zero clipping, comfortable quiet bedtime loudness ~ -19 LUFS feel)
    pk = float(max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)), 1e-6))
    if pk > 0.78:
        scale = 0.78 / pk
        mix_l *= scale
        mix_r *= scale
    mix_l = np.tanh(mix_l * 1.06) / 1.06
    mix_r = np.tanh(mix_r * 1.06) / 1.06

    # Interleave stereo int16 -> WAV -> silky 44.1kHz stereo MP3
    stereo = np.empty(total_n * 2, dtype=np.int16)
    stereo[0::2] = np.clip(mix_l * 32767.0, -32768, 32767).astype(np.int16)
    stereo[1::2] = np.clip(mix_r * 32767.0, -32768, 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp_wav = tf.name
    try:
        with wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(stereo.tobytes())
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", tmp_wav, "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame",
                "-b:a", bitrate, "-joint_stereo", "1", out_mp3_path,
            ],
            check=True,
        )
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    size_mb = os.path.getsize(out_mp3_path) / (1024 * 1024)
    print(f"[sleep-master] Done! {out_mp3_path} ({total_sec/60.0:.2f} min, {size_mb:.2f} MB @ {bitrate})", flush=True)
    out_meta = dict(meta)
    out_meta["duration_sec"] = round(total_sec, 1)
    out_meta["audio_file"] = os.path.basename(out_mp3_path)
    out_meta["audio_url"] = f"./audio/sleep/{os.path.basename(out_mp3_path)}"
    out_meta["audio_sha"] = hashlib.sha256(open(out_mp3_path, "rb").read()).hexdigest()[:10]
    out_meta["mastered_at"] = datetime.datetime.now(PT_TZ).isoformat(timespec="seconds")
    return out_meta


def load_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        try:
            return json.loads(open(MANIFEST_PATH, encoding="utf-8").read())
        except Exception:
            pass
    return {"schema": "kyoto-sleep-library/1", "episodes": []}


def save_episode_to_manifest(ep_meta: dict) -> dict:
    os.makedirs(SLEEP_DIR, exist_ok=True)
    mf = load_manifest()
    eps = [e for e in (mf.get("episodes") or []) if str(e.get("date")) != str(ep_meta.get("date"))]
    eps.append(ep_meta)
    # Newest night first; NEVER auto-drop recent nights, keep up to MAX_ARCHIVED_EPISODES
    eps.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
    if len(eps) > MAX_ARCHIVED_EPISODES:
        dropped = eps[MAX_ARCHIVED_EPISODES:]
        eps = eps[:MAX_ARCHIVED_EPISODES]
        for d in dropped:
            af = d.get("audio_file")
            if af:
                p = os.path.join(SLEEP_DIR, af)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
    mf["schema"] = "kyoto-sleep-library/1"
    mf["updated_at"] = datetime.datetime.now(PT_TZ).isoformat(timespec="seconds")
    mf["episodes"] = eps
    open(MANIFEST_PATH, "w", encoding="utf-8").write(json.dumps(mf, ensure_ascii=False, indent=2))
    print(f"[sleep-master] Manifest updated: {len(eps)} episode(s) in library.", flush=True)
    return mf


def pull_latest_from_relay(topic: str = DEFAULT_SLEEP_RELAY_TOPIC, force_date: str = "") -> list[str]:
    """
    Pulls any new bedtime story metadata + voice stem from ntfy.sh relay,
    masters it with Kyoto Sleep Soundscape, and adds it to the persistent library.
    Returns list of newly ingested dates.
    """
    mf = load_manifest()
    existing_by_date = {str(e.get("date") or ""): e for e in (mf.get("episodes") or [])}

    url = f"https://ntfy.sh/{topic}/json?poll=1&since=all"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "N3SleepPuller/1.0"})
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            lines = resp.read().decode("utf-8", errors="replace").splitlines()
    except Exception as e:
        print(f"[sleep-pull] Relay poll skipped: {e}", flush=True)
        return []

    buckets: dict[str, dict] = {}
    for line in lines:
        try:
            ev = json.loads(line)
            if ev.get("event") != "message":
                continue
            obj = json.loads(ev.get("message") or "")
            if obj.get("v") == 1 and obj.get("kind") == "sleep_story":
                uid = f"{obj.get('date')}_{obj.get('uid')}"
                b = buckets.setdefault(
                    uid,
                    {
                        "date": str(obj.get("date") or ""),
                        "n": int(obj.get("n", 0)),
                        "sha": str(obj.get("sha") or ""),
                        "ts": int(ev.get("time") or 0),
                        "parts": {},
                    },
                )
                b["ts"] = max(b["ts"], int(ev.get("time") or 0))
                b["parts"][int(obj.get("i", -1))] = str(obj.get("d") or "")
        except Exception:
            continue

    ingested: list[str] = []
    # Process newest uploads first so if a night was re-rendered, the latest version wins cleanly
    for uid, b in sorted(buckets.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True):
        date_str = b["date"]
        if not date_str or b["n"] <= 0 or len(b["parts"]) != b["n"]:
            continue
        if force_date and date_str != force_date:
            continue
        prev = existing_by_date.get(date_str)
        if prev and "fallback" not in str(prev.get("voice_engine") or "") and (not force_date or date_str in ingested):
            continue  # Already have studio Gemini TTS version for this night!
        try:
            b64 = "".join(b["parts"][i] for i in range(b["n"]))
            raw = gzip.decompress(base64.b64decode(b64))
            if hashlib.sha256(raw).hexdigest()[:12] != b["sha"]:
                print(f"[sleep-pull] SHA mismatch for {date_str}, skipping.", flush=True)
                continue
            packet = json.loads(raw.decode("utf-8"))
            att_url = str(packet.get("voice_attachment_url") or "")
            if not att_url:
                continue
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_voice = tf.name
            try:
                vreq = urllib.request.Request(att_url, headers={"User-Agent": "N3SleepPuller/1.0"})
                with urllib.request.urlopen(vreq, timeout=90.0) as vresp:
                    vbytes = vresp.read()
                if len(vbytes) < 100_000:
                    print(f"[sleep-pull] Voice attachment too small ({len(vbytes)}B), skipping.", flush=True)
                    continue
                open(tmp_voice, "wb").write(vbytes)
                out_mp3 = os.path.join(SLEEP_DIR, f"sleep_{date_str}.mp3")
                ep_meta = master_bedtime_episode(tmp_voice, packet, out_mp3)
                ep_meta.pop("voice_attachment_url", None)
                save_episode_to_manifest(ep_meta)
                existing_by_date[date_str] = ep_meta
                ingested.append(date_str)
            finally:
                if os.path.exists(tmp_voice):
                    os.remove(tmp_voice)
        except Exception as e:
            print(f"[sleep-pull] Failed ingesting {date_str}: {e}", flush=True)
    return ingested


def main() -> int:
    parser = argparse.ArgumentParser(description="Kyoto Bedtime Soundscape Mastering & Relay Sync")
    parser.add_argument("--pull-relay", action="store_true", help="Pull any new studio bedtime stories from ntfy relay and master them")
    parser.add_argument("--master-voice", default="", help="Master a local voice stem WAV/MP3")
    parser.add_argument("--meta-json", default="", help="Metadata JSON paired with --master-voice")
    parser.add_argument("--bitrate", default="80k", help="Output stereo MP3 bitrate (default 80k)")
    parser.add_argument("--force-date", default="", help="Optional YYYY-MM-DD to force re-pull")
    args = parser.parse_args()

    if args.master_voice and args.meta_json:
        meta = json.loads(open(args.meta_json, encoding="utf-8").read())
        date_str = str(meta.get("date") or datetime.datetime.now(PT_TZ).date().isoformat())
        out_mp3 = os.path.join(SLEEP_DIR, f"sleep_{date_str}.mp3")
        ep_meta = master_bedtime_episode(args.master_voice, meta, out_mp3, bitrate=args.bitrate)
        save_episode_to_manifest(ep_meta)
        return 0

    if args.pull_relay:
        topic = (os.environ.get("SLEEP_RELAY_NTFY_TOPIC") or DEFAULT_SLEEP_RELAY_TOPIC).strip()
        got = pull_latest_from_relay(topic=topic, force_date=args.force_date)
        print(f"[sleep-master] Relay pull finished. Newly mastered: {got}", flush=True)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

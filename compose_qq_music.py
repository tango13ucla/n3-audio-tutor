#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Studio Procedural Composer for the "Qiang Qiang Three" (《锵锵三人行》) Broadcast Music Suite.
Generates 4 100% royalty-free, broadcast-mastered instrumental cues in `audio/`:
  - `qq_intro.mp3`  (~8.0s): Upbeat 126-BPM Jazz-Mambo salon theme + iconic "锵！锵！" (京小锣) hits & duckable tail
  - `qq_bumper.mp3` (~4.2s): Mid-episode "广告之后见" outgoing + incoming commercial bumper with "锵！锵！" stinger
  - `qq_sting.mp3`  (~1.9s): Light conversational chapter-turn jazz/marimba/woodblock sting
  - `qq_outro.mp3`  (~9.0s): Warm late-night salon closing theme (soft lead-in for voice-over + full combo fade-out)
"""
from __future__ import annotations
import math
import os
import subprocess
import tempfile
import wave
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SR = 48000

NOTE_SEMI = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def note_to_hz(note: str) -> float:
    m = note[:-1]
    octv = int(note[-1])
    midi = 12 * (octv + 1) + NOTE_SEMI[m]
    return midi_to_hz(midi)


def _mix_into(buf: np.ndarray, sig: np.ndarray, start_sec: float, gain: float = 1.0) -> None:
    idx = int(round(start_sec * SR))
    if idx < 0:
        sig = sig[-idx:]
        idx = 0
    if idx >= len(buf) or len(sig) == 0:
        return
    end = min(len(buf), idx + len(sig))
    buf[idx:end] += gain * sig[: end - idx]


def _one_pole_lp(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    rc = 1.0 / (2.0 * math.pi * max(20.0, cutoff_hz))
    dt = 1.0 / SR
    alpha = dt / (rc + dt)
    out = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (float(x[i]) - acc)
        out[i] = acc
    return out


def synth_xiaoluo_qiang(dur: float = 0.72, base_hz: float = 505.0, accent: float = 1.0) -> np.ndarray:
    """
    Physical model of the iconic Chinese Peking-opera small gong (`京小锣` "锵↗！")
    with its signature upward pitch glide + bronze inharmonic partials + crisp cymbal shimmer.
    """
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    # Upward pitch glide characteristic of convex-boss xiaoluo ("Qiang↗!")
    f_curve = base_hz * (1.0 + 0.135 * (1.0 - np.exp(-t / 0.048))) * (1.0 - 0.015 * t)
    phase_base = 2.0 * math.pi * np.cumsum(f_curve) / SR

    partials = [
        (1.000, 1.00, 3.4),
        (1.386, 0.62, 5.2),
        (1.942, 0.48, 7.5),
        (2.578, 0.34, 10.5),
        (3.215, 0.24, 14.0),
        (4.110, 0.16, 19.0),
        (5.290, 0.10, 25.0),
    ]
    sig = np.zeros(n, dtype=np.float64)
    for ratio, amp, decay in partials:
        # Slight shimmer detune beating on higher partials
        beat = 1.0 + 0.08 * np.sin(2.0 * math.pi * (5.5 + ratio * 1.7) * t)
        sig += amp * np.sin(phase_base * ratio) * np.exp(-t * decay) * beat

    # Crisp wooden-striker bronze transient + small hand-cymbal ("小镲") air
    rng = np.random.default_rng(int(base_hz * 100))
    noise = rng.standard_normal(n)
    # High-frequency metallic sheen via finite difference high-pass
    hp_noise = np.diff(noise, prepend=0.0)
    hp_noise = np.diff(hp_noise, prepend=0.0) * 0.25
    sheen = hp_noise * np.exp(-t * 26.0) * 0.42
    wood_click = np.sin(2.0 * math.pi * 1650.0 * t) * np.exp(-t * 140.0) * 0.35

    attack = np.minimum(1.0, t / 0.0022)
    out = (sig * 0.55 + sheen + wood_click) * attack * accent
    return np.tanh(out * 1.25).astype(np.float32)


def synth_upright_bass(note: str, dur: float, vel: float = 1.0) -> np.ndarray:
    """Karplus-Strong plucked acoustic upright double bass with warm wooden body resonance."""
    hz = note_to_hz(note)
    n = int(SR * (dur + 0.08))
    period = max(8, int(round(SR / hz)))
    rng = np.random.default_rng(int(hz * 97) + int(dur * 1000))
    # Smooth finger-pluck excitation (warm, not metallic)
    init = rng.uniform(-1.0, 1.0, period).astype(np.float64)
    init = np.convolve(init, np.hanning(9) / np.sum(np.hanning(9)), mode="same")

    buf = np.zeros(n, dtype=np.float64)
    buf[:period] = init
    damping = 0.9945
    blend = 0.42
    for i in range(period, n):
        buf[i] = damping * ((1.0 - blend) * buf[i - period] + blend * buf[i - period + 1])

    t = np.arange(n, dtype=np.float64) / SR
    # Add warm fundamental & 2nd harmonic woody body bloom
    body = (
        0.55 * np.sin(2.0 * math.pi * hz * t) * np.exp(-t * 3.6)
        + 0.24 * np.sin(2.0 * math.pi * hz * 2.0 * t) * np.exp(-t * 5.5)
    )
    env = np.minimum(1.0, t / 0.006) * np.exp(-t * 2.4)
    rel_start = int(SR * dur)
    if rel_start < n:
        rel_len = n - rel_start
        env[rel_start:] *= np.linspace(1.0, 0.0, rel_len)
    out = (buf * 0.75 + body) * env * vel
    return out.astype(np.float32)


def synth_jazz_horn(note: str, dur: float, style: str = "trumpet", vel: float = 1.0) -> np.ndarray:
    """Expressive Harmon-muted jazz trumpet / warm alto saxophone with gentle scoop & vibrato."""
    target_hz = note_to_hz(note)
    n = int(SR * (dur + 0.04))
    t = np.arange(n, dtype=np.float64) / SR

    # Subtle jazz pitch scoop on attack + warm delayed vibrato
    scoop = 1.0 - 0.022 * np.exp(-t / 0.018)
    vib_depth = 0.0045 * np.clip((t - 0.09) / 0.10, 0.0, 1.0)
    inst_hz = target_hz * scoop * (1.0 + vib_depth * np.sin(2.0 * math.pi * 5.6 * t))
    phase = 2.0 * math.pi * np.cumsum(inst_hz) / SR

    if style == "sax":
        # Warm reed spectrum (strong 1st, 2nd, 3rd, softer high harmonics)
        harms = [(1, 1.00), (2, 0.68), (3, 0.46), (4, 0.25), (5, 0.16), (6, 0.09), (7, 0.05)]
    else:
        # Crisp jazz brass / muted trumpet spectrum (bright mid-formant presence around 1.5-2.8kHz)
        harms = [(1, 0.82), (2, 0.95), (3, 0.78), (4, 0.54), (5, 0.36), (6, 0.22), (7, 0.12), (8, 0.06)]

    sig = np.zeros(n, dtype=np.float64)
    for k, amp in harms:
        if target_hz * k < SR * 0.44:
            # Brass brightness opens up on attack then mellows slightly
            bright_env = np.exp(-t * (0.6 * max(0, k - 2)))
            sig += amp * np.sin(phase * k) * bright_env

    # Soft breath chiff at tongue attack
    rng = np.random.default_rng(int(target_hz * 53))
    chiff = rng.standard_normal(n) * np.exp(-t * 95.0) * 0.08

    att = np.minimum(1.0, t / (0.014 if style == "trumpet" else 0.020))
    sustain_decay = np.exp(-t * 1.35)
    env = att * sustain_decay
    rel_idx = int(SR * dur)
    if rel_idx < n:
        env[rel_idx:] *= np.linspace(1.0, 0.0, n - rel_idx)
    out = np.tanh((sig * 0.42 + chiff) * env * vel * 1.15)
    return out.astype(np.float32)


def synth_marimba(note: str, dur: float = 0.28, vel: float = 1.0) -> np.ndarray:
    """Warm rosewood marimba / vibraphone bar with authentic 1 : 3.99 : 9.2tuning."""
    hz = note_to_hz(note)
    n = int(SR * max(dur, 0.34))
    t = np.arange(n, dtype=np.float64) / SR
    sig = (
        1.00 * np.sin(2.0 * math.pi * hz * t) * np.exp(-t * 7.5)
        + 0.34 * np.sin(2.0 * math.pi * hz * 3.99 * t) * np.exp(-t * 22.0)
        + 0.11 * np.sin(2.0 * math.pi * hz * 9.20 * t) * np.exp(-t * 48.0)
    )
    mallet = np.sin(2.0 * math.pi * 1150.0 * t) * np.exp(-t * 180.0) * 0.18
    env = np.minimum(1.0, t / 0.0025)
    return ((sig * 0.58 + mallet) * env * vel).astype(np.float32)


def synth_rhodes_chord(notes: list[str], dur: float, vel: float = 1.0) -> np.ndarray:
    """Warm Rhodes / lounge jazz electric piano chord comping."""
    n = int(SR * (dur + 0.12))
    t = np.arange(n, dtype=np.float64) / SR
    sig = np.zeros(n, dtype=np.float64)
    for idx, nt in enumerate(notes):
        hz = note_to_hz(nt)
        tine = 0.16 * np.sin(2.0 * math.pi * hz * 3.0 * t) * np.exp(-t * 14.0)
        tone = (
            1.00 * np.sin(2.0 * math.pi * hz * t) * np.exp(-t * 2.6)
            + 0.28 * np.sin(2.0 * math.pi * hz * 2.0 * t) * np.exp(-t * 4.8)
        )
        # Subtle micro-strum across chord voices (6ms per voice)
        shift = int(idx * 0.005 * SR)
        voice = tone + tine
        if shift > 0 and shift < n:
            sig[shift:] += voice[: n - shift]
        else:
            sig += voice
    env = np.minimum(1.0, t / 0.008)
    rel_idx = int(SR * dur)
    if rel_idx < n:
        env[rel_idx:] *= np.linspace(1.0, 0.0, n - rel_idx)
    return (sig / max(1, len(notes)) * env * vel * 0.55).astype(np.float32)


def synth_woodblock(pitch_hz: float = 960.0, vel: float = 1.0) -> np.ndarray:
    """Crisp Chinese bangzi / temple woodblock (`梆子`) percussion accent."""
    n = int(SR * 0.09)
    t = np.arange(n, dtype=np.float64) / SR
    sig = (
        1.0 * np.sin(2.0 * math.pi * pitch_hz * t) * np.exp(-t * 58.0)
        + 0.45 * np.sin(2.0 * math.pi * (pitch_hz * 1.54) * t) * np.exp(-t * 95.0)
    )
    env = np.minimum(1.0, t / 0.0012)
    return (sig * env * vel * 0.52).astype(np.float32)


def synth_brush_drum(kind: str, vel: float = 1.0) -> np.ndarray:
    """Jazz brush snare, soft kick, and swing ride cymbal."""
    rng = np.random.default_rng({"kick": 11, "brush": 22, "ride": 33}.get(kind, 44))
    if kind == "kick":
        n = int(SR * 0.18)
        t = np.arange(n, dtype=np.float64) / SR
        f = 54.0 + 68.0 * np.exp(-t / 0.022)
        ph = 2.0 * math.pi * np.cumsum(f) / SR
        sig = np.sin(ph) * np.exp(-t * 16.0) * np.minimum(1.0, t / 0.002)
        return (sig * vel * 0.58).astype(np.float32)
    if kind == "brush":
        n = int(SR * 0.16)
        t = np.arange(n, dtype=np.float64) / SR
        nz = rng.standard_normal(n)
        nz = np.diff(nz, prepend=0.0) * 0.45
        body = np.sin(2.0 * math.pi * 210.0 * t) * np.exp(-t * 38.0) * 0.25
        env = np.minimum(1.0, t / 0.004) * np.exp(-t * 19.0)
        return ((nz * env * 0.52 + body) * vel).astype(np.float32)
    # Swing ride cymbal
    n = int(SR * 0.30)
    t = np.arange(n, dtype=np.float64) / SR
    nz = rng.standard_normal(n)
    hp = np.diff(np.diff(nz, prepend=0.0), prepend=0.0) * 0.22
    bell = (
        0.18 * np.sin(2.0 * math.pi * 2960.0 * t) * np.exp(-t * 22.0)
        + 0.12 * np.sin(2.0 * math.pi * 4310.0 * t) * np.exp(-t * 30.0)
    )
    env = np.minimum(1.0, t / 0.0015) * np.exp(-t * 12.5)
    return ((hp * env + bell) * vel * 0.38).astype(np.float32)


def add_swing_groove_bar(buf: np.ndarray, bar_start: float, beat: float, intensity: float = 1.0) -> None:
    """Adds 1 bar (4 beats) of lively jazz-salon brush + ride + woodblock rhythm."""
    for b in range(4):
        bt = bar_start + b * beat
        if b in (0, 2):
            _mix_into(buf, synth_brush_drum("kick", 0.85 * intensity), bt)
        else:
            _mix_into(buf, synth_brush_drum("brush", 0.82 * intensity), bt)
        _mix_into(buf, synth_brush_drum("ride", 0.78 * intensity), bt)
        if b in (1, 3):
            # Swing triplet skip-beat ("ding-ding-da-ding")
            _mix_into(buf, synth_brush_drum("ride", 0.52 * intensity), bt + beat * 0.66)
    # Playful Mambo/Chinese woodblock syncopation on beat 1.5 and 3.5
    _mix_into(buf, synth_woodblock(1020.0, 0.55 * intensity), bar_start + beat * 1.5)
    _mix_into(buf, synth_woodblock(860.0, 0.48 * intensity), bar_start + beat * 3.0)


def build_intro_cue() -> np.ndarray:
    """
    ~8.0s Authentic 《锵锵三人行》 Opening Theme:
    - 0.00-0.85s: Crisp woodblock pickup + signature double "锵↗！锵↗！" gong & brass hit
    - 0.85-6.55s: 3-bar upbeat 126-BPM Jazz-Mambo conversational brass/sax/marimba/walking-bass groove
    - 6.55-8.10s: Final turnaround landing on "锵↗！锵↗！" + warm 1.55s duckable tail
    """
    bpm = 128.0
    beat = 60.0 / bpm  # 0.46875s
    total_dur = 8.15
    buf = np.zeros(int(SR * total_dur), dtype=np.float32)

    # Pickup woodblocks + Double "Qiang! Qiang!" title call
    _mix_into(buf, synth_woodblock(1080.0, 0.75), 0.04)
    _mix_into(buf, synth_woodblock(910.0, 0.85), 0.17)

    # Iconic Hit 1 & Hit 2: "锵！ 锵！"
    t_q1 = 0.30
    t_q2 = 0.58
    _mix_into(buf, synth_xiaoluo_qiang(0.55, 505.0, 0.92), t_q1)
    _mix_into(buf, synth_rhodes_chord(["G3", "B3", "E4", "A4"], 0.22, 0.85), t_q1)
    _mix_into(buf, synth_jazz_horn("D5", 0.18, "trumpet", 0.72), t_q1)
    _mix_into(buf, synth_brush_drum("kick", 0.9), t_q1)

    _mix_into(buf, synth_xiaoluo_qiang(0.68, 535.0, 1.00), t_q2)
    _mix_into(buf, synth_rhodes_chord(["A3", "C#4", "F#4", "B4"], 0.28, 0.90), t_q2)
    _mix_into(buf, synth_jazz_horn("E5", 0.24, "trumpet", 0.80), t_q2)
    _mix_into(buf, synth_brush_drum("brush", 0.9), t_q2)

    # Groove starts at t0 = 0.95s (3 bars of 4/4 = 12 beats = 5.625s -> lands on final hit at 6.575s!)
    t0 = 0.95
    for bar_i in range(3):
        add_swing_groove_bar(buf, t0 + bar_i * 4 * beat, beat, intensity=0.95)

    # Walking Upright Bass across 3 bars: G6 -> Em7 -> Am9 -> D13
    bass_notes = [
        # Bar 1 (G6 -> Em7)
        ("G2", 0.0), ("B2", 1.0), ("D3", 2.0), ("F2", 3.0),
        # Bar 2 (Em7 -> Am9)
        ("E2", 4.0), ("G2", 5.0), ("B2", 6.0), ("G#2", 7.0),
        # Bar 3 (Am9 -> D13 turnaround)
        ("A2", 8.0), ("C3", 9.0), ("D2", 10.0), ("F#2", 11.0),
    ]
    for nt, b_off in bass_notes:
        _mix_into(buf, synth_upright_bass(nt, beat * 0.92, 0.95), t0 + b_off * beat)

    # Syncopated Rhodes Jazz Chord Comping
    chords = [
        (["B3", "D4", "E4", "A4"], 0.0, 0.75),
        (["B3", "D4", "E4", "A4"], 1.5, 0.65),
        (["G3", "B3", "D4", "F#4"], 4.0, 0.72),
        (["G3", "B3", "D4", "F#4"], 5.5, 0.65),
        (["G3", "B3", "C4", "E4"], 8.0, 0.75),
        (["F#3", "C4", "E4", "B4"], 10.0, 0.82),
    ]
    for notes, b_off, v in chords:
        _mix_into(buf, synth_rhodes_chord(notes, beat * 1.1, v), t0 + b_off * beat)

    # Playful Conversational Melody (Call: Muted Trumpet, Response: Alto Sax + Marimba!)
    # Bar 1 Call (Trumpet + Marimba sparkle): bouncy pentatonic-blues salon motif
    melody = [
        ("D5", 0.0, 0.45, "trumpet", 0.85),
        ("E5", 0.5, 0.45, "trumpet", 0.82),
        ("G5", 1.0, 0.65, "trumpet", 0.92),
        ("E5", 1.66, 0.34, "trumpet", 0.78),
        ("D5", 2.0, 0.48, "trumpet", 0.86),
        ("B4", 2.5, 0.85, "trumpet", 0.84),
        # Bar 2 Response (Warm Alto Sax answering wittily)
        ("E4", 4.0, 0.45, "sax", 0.88),
        ("G4", 4.5, 0.45, "sax", 0.86),
        ("B4", 5.0, 0.65, "sax", 0.94),
        ("D5", 5.66, 0.34, "sax", 0.84),
        ("B4", 6.0, 0.48, "sax", 0.88),
        ("A4", 6.5, 0.85, "sax", 0.85),
        # Bar 3 Trio Together (Trumpet + Sax harmony ascending to turnaround!)
        ("A4", 8.0, 0.45, "trumpet", 0.85),
        ("B4", 8.5, 0.45, "trumpet", 0.88),
        ("D5", 9.0, 0.65, "trumpet", 0.92),
        ("E5", 10.0, 0.48, "trumpet", 0.95),
        ("F#5", 10.5, 0.48, "trumpet", 0.95),
        ("A5", 11.0, 0.65, "trumpet", 0.92),
    ]
    for nt, b_off, b_len, inst, v in melody:
        _mix_into(buf, synth_jazz_horn(nt, b_len * beat, inst, v), t0 + b_off * beat)
        if inst == "trumpet" and b_off in (0.0, 1.0, 2.0, 9.0, 10.0, 11.0):
            _mix_into(buf, synth_marimba(nt, 0.24, 0.55), t0 + b_off * beat)

    #Sax harmony under Bar 3 turnaround
    for nt, b_off, b_len in [("E4", 8.0, 0.9), ("G4", 9.0, 0.9), ("C5", 10.0, 0.9), ("D5", 11.0, 0.7)]:
        _mix_into(buf, synth_jazz_horn(nt, b_len * beat, "sax", 0.68), t0 + b_off * beat)

    # Final Cadence at Beat 12 (t ≈ 6.575s): Signature "锵！锵！" landing into G6/9 warm chord tail!
    t_fin1 = t0 + 12.0 * beat
    t_fin2 = t0 + 12.66 * beat
    _mix_into(buf, synth_xiaoluo_qiang(0.60, 505.0, 0.88), t_fin1)
    _mix_into(buf, synth_upright_bass("D2", 0.28, 0.95), t_fin1)
    _mix_into(buf, synth_jazz_horn("E5", 0.24, "trumpet", 0.82), t_fin1)

    _mix_into(buf, synth_xiaoluo_qiang(1.15, 540.0, 1.00), t_fin2)
    _mix_into(buf, synth_upright_bass("G2", 1.15, 1.00), t_fin2)
    _mix_into(buf, synth_rhodes_chord(["B3", "D4", "E4", "A4", "D5"], 1.15, 0.92), t_fin2)
    _mix_into(buf, synth_jazz_horn("G5", 0.85, "trumpet", 0.85), t_fin2)
    _mix_into(buf, synth_jazz_horn("B4", 0.90, "sax", 0.72), t_fin2)
    _mix_into(buf, synth_marimba("G5", 0.45, 0.75), t_fin2)

    # Smooth fade-out on final 0.5s
    fade_n = int(SR * 0.55)
    buf[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    return buf


def build_bumper_cue() -> np.ndarray:
    """
    ~4.2s Classic 《锵锵三人行》 Commercial Ad-Break Bumper ("广告之后见！"):
    - Part A (0.00-1.75s): Outgoing snappy brass/marimba flourish + "锵！锵！"
    - Breath (1.75-2.15s): Brief studio bumper air
    - Part B (2.15-4.15s): Incoming walking-bass & trumpet pickup + crisp "锵！" into "欢迎回到《锵锵三人行》！"
    """
    bpm = 130.0
    beat = 60.0 / bpm
    total_dur = 4.20
    buf = np.zeros(int(SR * total_dur), dtype=np.float32)

    # Part A: Outgoing flourish
    _mix_into(buf, synth_upright_bass("A2", beat * 0.9, 0.9), 0.02)
    _mix_into(buf, synth_upright_bass("D2", beat * 0.9, 0.92), 0.02 + beat)
    _mix_into(buf, synth_rhodes_chord(["G3", "C4", "E4", "A4"], beat * 0.8, 0.75), 0.02)
    _mix_into(buf, synth_rhodes_chord(["F#3", "C4", "E4", "B4"], beat * 0.8, 0.82), 0.02 + beat)
    for nt, bo in [("A4", 0.0), ("B4", 0.5), ("D5", 1.0), ("E5", 1.5)]:
        _mix_into(buf, synth_jazz_horn(nt, 0.42 * beat, "trumpet", 0.85), 0.02 + bo * beat)
        _mix_into(buf, synth_marimba(nt, 0.20, 0.55), 0.02 + bo * beat)
    _mix_into(buf, synth_brush_drum("ride", 0.75), 0.02)
    _mix_into(buf, synth_brush_drum("brush", 0.80), 0.02 + beat)

    # Outgoing "锵！锵！"
    q_out1 = 0.02 + 2.0 * beat
    q_out2 = 0.02 + 2.55 * beat
    _mix_into(buf, synth_xiaoluo_qiang(0.45, 505.0, 0.88), q_out1)
    _mix_into(buf, synth_xiaoluo_qiang(0.65, 538.0, 0.96), q_out2)
    _mix_into(buf, synth_upright_bass("G2", 0.55, 0.95), q_out2)
    _mix_into(buf, synth_rhodes_chord(["B3", "D4", "E4", "G4"], 0.50, 0.85), q_out2)
    _mix_into(buf, synth_jazz_horn("G5", 0.42, "trumpet", 0.82), q_out2)

    # Part B: Incoming return-from-break pickup (starts at 2.15s)
    t_in = 2.15
    _mix_into(buf, synth_woodblock(1040.0, 0.70), t_in)
    _mix_into(buf, synth_woodblock(880.0, 0.75), t_in + 0.14)
    for nt, bo in [("D2", 0.35), ("E2", 1.15), ("G2", 1.95)]:
        _mix_into(buf, synth_upright_bass(nt, 0.38, 0.92), t_in + bo * beat)
    for nt, bo, ln in [("D5", 0.35, 0.4), ("E5", 0.80, 0.4), ("G5", 1.25, 0.55), ("A5", 1.95, 0.75)]:
        _mix_into(buf, synth_jazz_horn(nt, ln * beat, "sax" if bo < 1.2 else "trumpet", 0.85), t_in + bo * beat)
    t_in_hit = t_in + 1.95 * beat
    _mix_into(buf, synth_xiaoluo_qiang(0.85, 535.0, 0.95), t_in_hit)
    _mix_into(buf, synth_rhodes_chord(["B3", "D4", "E4", "A4"], 0.80, 0.88), t_in_hit)
    _mix_into(buf, synth_marimba("A5", 0.35, 0.65), t_in_hit)

    fade_n = int(SR * 0.40)
    buf[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    return buf


def build_sting_cue() -> np.ndarray:
    """~1.85s Subtle Salon Page-Turn Sting between non-ad-break stories."""
    total_dur = 1.85
    buf = np.zeros(int(SR * total_dur), dtype=np.float32)
    _mix_into(buf, synth_woodblock(980.0, 0.55), 0.03)
    _mix_into(buf, synth_upright_bass("D3", 0.28, 0.80), 0.05)
    _mix_into(buf, synth_marimba("A4", 0.25, 0.68), 0.05)
    _mix_into(buf, synth_upright_bass("E3", 0.28, 0.82), 0.31)
    _mix_into(buf, synth_marimba("B4", 0.25, 0.72), 0.31)
    _mix_into(buf, synth_jazz_horn("D5", 0.22, "sax", 0.65), 0.31)

    _mix_into(buf, synth_upright_bass("G2", 0.95, 0.90), 0.58)
    _mix_into(buf, synth_rhodes_chord(["B3", "D4", "E4", "A4"], 0.95, 0.80), 0.58)
    _mix_into(buf, synth_marimba("E5", 0.42, 0.75), 0.58)
    _mix_into(buf, synth_xiaoluo_qiang(0.85, 525.0, 0.52), 0.58)
    _mix_into(buf, synth_brush_drum("ride", 0.65), 0.58)

    fade_n = int(SR * 0.45)
    buf[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    return buf


def build_outro_cue() -> np.ndarray:
    """
    ~9.2s Warm Late-Night 《锵锵三人行》 Closing Theme:
    - 0.00-2.60s: Gentle Rhodes + walking upright bass + brush ride bed (designed to sit smoothly underneath Wen Tao's final sign-off!)
    - 2.60-9.20s: Swells up as Wen Tao finishes "咱们明天见！", playing the warm alto-sax & trumpet evening reprise + final gentle "锵↗！" fade-out!
    """
    bpm = 116.0  # Slightly more relaxed, warm late-night salon tempo
    beat = 60.0 / bpm
    total_dur = 9.20
    buf = np.zeros(int(SR * total_dur), dtype=np.float32)

    # Bar 0 (0.00 - 2.07s): Soft underscore while Wen Tao delivers final farewell
    add_swing_groove_bar(buf, 0.10, beat, intensity=0.45)
    for nt, bo in [("G2", 0.0), ("B2", 1.0), ("E2", 2.0), ("G2", 3.0)]:
        _mix_into(buf, synth_upright_bass(nt, beat * 0.95, 0.52), 0.10 + bo * beat)
    _mix_into(buf, synth_rhodes_chord(["B3", "D4", "E4", "A4"], beat * 1.8, 0.44), 0.10)
    _mix_into(buf, synth_rhodes_chord(["G3", "B3", "D4", "F#4"], beat * 1.8, 0.44), 0.10 + 2.0 * beat)

    # Bars 1 & 2 (2.17 - 6.31s): Full warm combo swells in after sign-off
    t1 = 0.10 + 4.0 * beat
    for bar_i in range(2):
        add_swing_groove_bar(buf, t1 + bar_i * 4 * beat, beat, intensity=0.85)

    outro_bass = [
        ("A2", 0.0), ("C3", 1.0), ("D2", 2.0), ("F#2", 3.0),
        ("G2", 4.0), ("E2", 5.0), ("A2", 6.0), ("D2", 7.0),
    ]
    for nt, bo in outro_bass:
        _mix_into(buf, synth_upright_bass(nt, beat * 0.92, 0.90), t1 + bo * beat)

    outro_chords = [
        (["G3", "B3", "C4", "E4"], 0.0, 0.74),
        (["F#3", "C4", "E4", "A4"], 2.0, 0.76),
        (["B3", "D4", "E4", "A4"], 4.0, 0.78),
        (["F#3", "C4", "E4", "B4"], 6.0, 0.80),
    ]
    for notes, bo, v in outro_chords:
        _mix_into(buf, synth_rhodes_chord(notes, beat * 1.6, v), t1 + bo * beat)

    # Warm Alto Sax & Muted Trumpet nostalgic reprise of the Qiang-Qiang motif
    outro_mel = [
        ("E4", 0.0, 0.5, "sax", 0.84),
        ("G4", 0.5, 0.5, "sax", 0.86),
        ("B4", 1.0, 0.9, "sax", 0.90),
        ("A4", 2.0, 0.6, "sax", 0.86),
        ("F#4", 2.66, 0.9, "sax", 0.82),
        ("D5", 4.0, 0.5, "trumpet", 0.82),
        ("E5", 4.5, 0.5, "trumpet", 0.84),
        ("G5", 5.0, 0.9, "trumpet", 0.88),
        ("E5", 6.0, 0.5, "trumpet", 0.84),
        ("D5", 6.5, 0.6, "trumpet", 0.82),
    ]
    for nt, bo, ln, inst, v in outro_mel:
        _mix_into(buf, synth_jazz_horn(nt, ln * beat, inst, v), t1 + bo * beat)
        if bo in (1.0, 4.0, 5.0):
            _mix_into(buf, synth_marimba(nt, 0.28, 0.50), t1 + bo * beat)

    # Final Resolution Chord + Gentle Signature "锵↗！" Bell-Gong & Fade-out
    t_end = t1 + 8.0 * beat
    _mix_into(buf, synth_upright_bass("G2", 2.1, 0.95), t_end)
    _mix_into(buf, synth_rhodes_chord(["G3", "B3", "D4", "E4", "A4"], 2.2, 0.88), t_end)
    _mix_into(buf, synth_jazz_horn("B4", 1.6, "sax", 0.76), t_end)
    _mix_into(buf, synth_jazz_horn("G5", 1.4, "trumpet", 0.72), t_end)
    _mix_into(buf, synth_marimba("G5", 0.55, 0.65), t_end)
    _mix_into(buf, synth_xiaoluo_qiang(1.4, 528.0, 0.68), t_end + 0.04)

    fade_in = int(SR * 0.25)
    buf[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    fade_out = int(SR * 1.45)
    buf[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32) ** 1.5
    return buf


def master_to_mp3(samples: np.ndarray, out_mp3: str, target_i_lufs: float = -18.5) -> None:
    """Writes 48kHz PCM WAV and runs ffmpeg studio room ambience + EBU R128 loudness mastering."""
    peak = float(np.max(np.abs(samples))) or 1.0
    norm = np.clip(samples / peak * 0.85, -0.99, 0.99)
    pcm16 = (norm * 32767.0).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        raw_wav = tf.name
    try:
        with wave.open(raw_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(pcm16.tobytes())

        af = (
            "highpass=f=45,"
            "lowpass=f=10500,"
            "aecho=0.8:0.86:24|41:0.15|0.09,"
            f"loudnorm=I={target_i_lufs}:TP=-5.0:LRA=8"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", raw_wav,
                "-af", af,
                "-ar", "24000", "-ac", "1", "-b:a", "64k", "-c:a", "libmp3lame",
                out_mp3,
            ],
            check=True,
        )
    finally:
        try:
            os.remove(raw_wav)
        except OSError:
            pass


def ensure_qq_music_assets(force: bool = False) -> dict[str, str]:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    paths = {
        "intro": os.path.join(AUDIO_DIR, "qq_intro.mp3"),
        "bumper": os.path.join(AUDIO_DIR, "qq_bumper.mp3"),
        "sting": os.path.join(AUDIO_DIR, "qq_sting.mp3"),
        "outro": os.path.join(AUDIO_DIR, "qq_outro.mp3"),
    }
    builders = {
        "intro": (build_intro_cue, -21.0),
        "bumper": (build_bumper_cue, -21.5),
        "sting": (build_sting_cue, -24.0),
        "outro": (build_outro_cue, -21.5),
    }
    for key, path in paths.items():
        if force or not os.path.exists(path) or os.path.getsize(path) < 1024:
            fn, lufs = builders[key]
            master_to_mp3(fn(), path, target_i_lufs=lufs)
    return paths


if __name__ == "__main__":
    out = ensure_qq_music_assets(force=True)
    for k, p in out.items():
        dur = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", p],
            text=True,
        ).strip()
        print(f"Rendered {k:6s} -> {p} ({float(dur):.2f}s, {os.path.getsize(p)} bytes)")

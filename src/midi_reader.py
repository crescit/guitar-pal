"""
guitar-buddy: MIDI reader — parse a .mid file into timed note events (seconds).

Pure data layer: given a MIDI file it returns sorted note events with
wall-clock start/end in seconds (constant-tempo assumption, taken from the
first SetTempo meta; default 120 bpm). Also supports writing a simple polyphonic
track to a file so tests can round-trip.

Design keeps the CV layer agnostic: a "note event" is just
(start_sec, end_sec, midi_note, velocity).
"""
from __future__ import annotations

import mido


class NoteEvent:
    __slots__ = ("start", "end", "note", "velocity")

    def __init__(self, start, end, note, velocity):
        self.start = float(start)
        self.end = float(end)
        self.note = int(note)
        self.velocity = int(velocity)

    @property
    def duration(self):
        return self.end - self.start

    def __repr__(self):
        return (f"NoteEvent(start={self.start:.3f},end={self.end:.3f},"
                f"note={self.note},vel={self.velocity})")


def _seconds_per_tick(mid):
    tempo_us = 500000  # 120 bpm default
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempo_us = msg.tempo
                break
        else:
            continue
        break
    return (tempo_us / 1e6) / mid.ticks_per_beat


def read_midi(path):
    """Parse a .mid file -> list[NoteEvent] sorted by start time."""
    mid = mido.MidiFile(path)
    spc = _seconds_per_tick(mid)
    active = {}          # (channel, note) -> (start_tick, velocity)
    events = []

    for track in mid.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type == "note_on":
                key = (msg.channel, msg.note)
                if msg.velocity == 0 and key in active:
                    start_tick, vel = active.pop(key)
                    events.append(NoteEvent(start_tick * spc, t * spc,
                                            msg.note, vel))
                elif msg.velocity > 0:
                    active[key] = (t, msg.velocity)
            elif msg.type == "note_off":
                key = (msg.channel, msg.note)
                if key in active:
                    start_tick, vel = active.pop(key)
                    events.append(NoteEvent(start_tick * spc, t * spc,
                                             msg.note, vel))

    # any still-active notes (unclosed) -> extend to file end
    if active:
        end_tick = mid.length
        for (ch, note), (st, vel) in active.items():
            events.append(NoteEvent(st * spc, end_tick * spc, note, vel))

    events.sort(key=lambda e: (e.start, e.note))
    return events


def write_track(path, note_seqs, tempo_bpm=120, ticks_per_beat=480, track_name="guitar"):
    """Write a simple polyphonic MIDI. note_seqs: list of (start_beats,
    duration_beats, midi_note, velocity) tuples. Writes one track."""
    tpb = ticks_per_beat
    msgs = []  # (tick, message)
    for start_b, dur_b, note, vel in note_seqs:
        on_tick = int(round(start_b * tpb))
        off_tick = int(round((start_b + dur_b) * tpb))
        msgs.append((on_tick, mido.Message("note_on", note=note, velocity=vel)))
        msgs.append((off_tick, mido.Message("note_off", note=note, velocity=0)))
    # sort by tick; tie -> note_off before note_on (close old, then open new)
    msgs.sort(key=lambda m: (m[0], 1 if m[1].type == "note_on" else 0))

    mid = mido.MidiFile(ticks_per_beat=tpb)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm), time=0))
    track.append(mido.MetaMessage("track_name", name=track_name, time=0))
    cur = 0
    for tick, msg in msgs:
        track.append(mido.Message(msg.type, note=msg.note, velocity=msg.velocity,
                                  time=max(tick - cur, 0)))
        cur = tick
    mid.tracks.append(track)
    mid.save(path)
    return path

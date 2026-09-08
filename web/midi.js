/* guitar-buddy web: minimal Standard MIDI File parser (in-browser).
   Returns timed note events {midi, start, end, vel} in seconds. */
"use strict";

function parseMIDI(buf) {
  const u = new Uint8Array(buf);
  let p = 0;

  function readStr(n) {
    const s = String.fromCharCode.apply(null, u.slice(p, p + n));
    p += n;
    return s;
  }
  function readVLQ() {
    let val = 0, b;
    do { b = u[p++]; val = (val << 7) | (b & 0x7f); } while (b & 0x80);
    return val;
  }
  function readU16() { const v = (u[p] << 8) | u[p + 1]; p += 2; return v; }
  function readU32() { const v = ((u[p] << 24) | (u[p + 1] << 16) | (u[p + 2] << 8) | u[p + 3]) >>> 0; p += 4; return v; }

  if (readStr(4) !== "MThd") throw new Error("Not a MIDI file (missing MThd).");
  readU32();
  readU16();                     // format
  const ntrks = readU16();
  const division = readU16();
  const ppq = division & 0x7fff;
  if (!ppq) throw new Error("SMPTE-division MIDI not supported.");

  // tempo map: [{tick, seconds-per-tick}] — default 120bpm (500000 us/qn)
  const tempoEvents = [{ tick: 0, spc: (500000 / 1e6) / ppq }];

  const active = new Map();      // key = ch*128+note -> {tick, vel}
  const notes = [];
  let maxTick = 0;
  let tempo = 500000;

  function close(ch, note, tick) {
    const k = ch * 128 + note;
    const a = active.get(k);
    if (a) {
      active.delete(k);
      notes.push({ midi: note, start: a.tick, end: tick, vel: a.vel });
    }
    if (tick > maxTick) maxTick = tick;
  }

  for (let t = 0; t < ntrks; t++) {
    if (readStr(4) !== "MTrk") { readU32(); continue; }
    const len = readU32();
    const end = p + len;
    let tick = 0, status = 0, metaJust = false;
    while (p < end) {
      metaJust = false;
      tick += readVLQ();
      let b = u[p];
      if (b & 0x80) { status = b; p++; } else b = status;
      const type = b & 0xf0, ch = b & 0x0f;

      if (type === 0x80 || type === 0x90) {
        const note = u[p++], vel = u[p++];
        if (type === 0x90 && vel > 0) {
          const k = ch * 128 + note;
          if (active.has(k)) close(ch, note, tick);   // reopen -> close old first
          active.set(k, { tick, vel });
        } else close(ch, note, tick);
      } else if (type === 0xA0 || type === 0xB0 || type === 0xE0) {
        p += 2;
      } else if (type === 0xC0 || type === 0xD0) {
        p += 1;
      } else if (b === 0xFF) {
        const mtype = u[p++];
        const mlen = readVLQ();
        if (mtype === 0x51 && mlen >= 3) {
          tempo = (u[p] << 16) | (u[p + 1] << 8) | u[p + 2];
          tempoEvents.push({ tick, spc: (tempo / 1e6) / ppq });
        }
        p += mlen;
        metaJust = true;
      }
    }
    // close any notes still ringing at the end of this track
    active.forEach((v, k) => { close((k >> 7) & 0xf, k & 0x7f, maxTick); });
    active.clear();
    p += 0; // no-op
  }

  const points = tempoEvents.slice().sort((a, b) => a.tick - b.tick);
  function secAt(tick0) {
    let sec = 0, prevT = 0, prevSpc = points[0].spc;
    for (let i = 1; i < points.length && tick0 > prevT; i++) {
      const pt = points[i];
      if (tick0 <= pt.tick) return sec + (tick0 - prevT) * prevSpc;
      sec += (pt.tick - prevT) * prevSpc;
      prevT = pt.tick; prevSpc = pt.spc;
    }
    return sec + (tick0 - prevT) * prevSpc;
  }

  const out = notes.map(n => ({ midi: n.midi, start: secAt(n.start), end: secAt(n.end), vel: n.vel }))
    .filter(n => n.end > n.start)
    .sort((a, b) => a.start - b.start);

  return {
    notes: out,
    duration: out.length ? out[out.length - 1].end : 0,
    division: ppq,
    tempoEvents: points,
  };
}

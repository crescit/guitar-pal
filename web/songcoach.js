/* guitar-buddy web: song coach — upload a MIDI, get the chord progression you
   need, and walk through it chord-by-chord with the step-by-step coach. */
"use strict";

const ROOT_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const QUALITIES = [
  { suffix: "",     intervals: [0,4,7]  },
  { suffix: "m",    intervals: [0,3,7]  },
  { suffix: "7",    intervals: [0,4,7,10]},
  { suffix: "maj7", intervals: [0,4,7,11]},
  { suffix: "m7",   intervals: [0,3,7,10]},
  { suffix: "sus4", intervals: [0,5,7]  },
  { suffix: "sus2", intervals: [0,2,7]  },
  { suffix: "5",    intervals: [0,7]    },
  { suffix: "dim",  intervals: [0,3,6] },
  { suffix: "aug",  intervals: [0,4,8] },
];

function nameChord(pcSet) {
  const s = Array.from(pcSet);
  if (!s.length) return "…";
  let best = null, bestScore = -1;
  for (const root of s) {
    const rel = new Set(s.map(pc => ((pc - root + 12) % 12)));
    for (const q of QUALITIES) {
      const exact = q.intervals.length === rel.size && q.intervals.every(iv => rel.has(iv));
      const contain = q.intervals.every(iv => rel.has(iv));
      const score = q.intervals.length + (exact ? 1000 : contain ? 0 : -100);
      if (score > bestScore) { bestScore = score; best = { root, suffix: q.suffix }; }
    }
  }
  if (!best) return ROOT_NAMES[Math.min(...s)];
  return ROOT_NAMES[best.root] + best.suffix;
}

function extractChords(notes) {
  if (!notes.length) return [];
  const bound = new Set();
  notes.forEach(n => { bound.add(n.start); bound.add(n.end); });
  const ts = Array.from(bound).sort((a, b) => a - b);
  const segs = [];
  for (let i = 0; i < ts.length - 1; i++) {
    const a = ts[i], b = ts[i + 1];
    if (b - a < 1e-6) continue;
    const active = notes.filter(n => n.start <= a + 1e-6 && n.end >= b - 1e-6);
    const pc = new Set(active.map(n => n.midi % 12));
    const name = nameChord(pc);
    segs.push({ start: a, end: b, name, notes: active });
  }
  // merge adjacent segments with the same name
  const merged = [];
  for (const s of segs) {
    const last = merged[merged.length - 1];
    if (last && last.name === s.name) last.end = s.end;
    else merged.push({ ...s });
  }
  return merged;
}

function isTaught(name) {
  return (window.guitarbuddy_coach && window.guitarbuddy_coach.CHORD_COACH.some(c => c.name === name)) || false;
}

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("songFile");
  const sampleBtn = document.getElementById("loadSample");
  const titleEl = document.getElementById("songTitle");
  const timelineEl = document.getElementById("timeline");
  const needEl = document.getElementById("chordNeed");
  const currentEl = document.getElementById("currentChord");
  const playBtn = document.getElementById("playBtn");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const resetBtn = document.getElementById("resetBtn");

  let chords = [], notes = [], currentIdx = -1, playing = false;
  let accum = 0, t0 = 0, timer = null;

  function nowSeconds() {
    return accum + (playing ? (performance.now() - t0) / 1000 : 0);
  }

  function driveCoach(name) {
    if (!isTaught(name) || !window.guitarbuddy_coach) return;
    const co = window.guitarbuddy_coach.CHORD_COACH.find(c => c.name === name);
    if (co) window.guitarbuddy_coach.selectChord(co);
  }

  function renderNow() {
    const seg = currentIdx >= 0 ? chords[currentIdx] : null;
    Array.from(timelineEl.children).forEach((el, i) => el.classList.toggle("now", i === currentIdx));
    if (seg) {
      currentEl.textContent = `${seg.name}  ·  ${seg.start.toFixed(1)}s–${seg.end.toFixed(1)}s`;
      currentEl.classList.add("lit");
      driveCoach(seg.name);
    } else {
      currentEl.textContent = "…";
      currentEl.classList.remove("lit");
    }
  }

  function setSong(nameStr, midiNotes, chordsOut) {
    notes = midiNotes; chords = chordsOut; currentIdx = -1; accum = 0;
    titleEl.textContent = nameStr;
    needEl.innerHTML = "";
    const uniq = Array.from(new Set(chords.map(c => c.name)));
    uniq.forEach(nm => {
      const chip = document.createElement("button");
      chip.className = "chip" + (isTaught(nm) ? " on" : "");
      chip.textContent = nm + (isTaught(nm) ? "  · taught" : "");
      chip.title = isTaught(nm) ? "We have a step-by-step guide for this one." : "Chord not in the coach library yet.";
      chip.addEventListener("click", () => driveCoach(nm));
      needEl.appendChild(chip);
    });
    // timeline
    timelineEl.innerHTML = "";
    const total = chords.length ? chords[chords.length - 1].end : 1;
    chords.forEach((c, i) => {
      const bar = document.createElement("div");
      bar.className = "cbar " + (isTaught(c.name) ? "taught" : "");
      bar.style.width = Math.max(2, (c.end - c.start) / total * 300) + "px";
      bar.innerHTML = `<span class="cname">${c.name}</span><span class="ctime">${c.start.toFixed(0)}s</span>`;
      bar.addEventListener("click", () => { currentIdx = i; accum = c.start; renderNow(); });
      timelineEl.appendChild(bar);
    });
    renderFullGuide();
    renderNow();
  }

  function loadNotes(midiEvents, fileLabel) {
    chords = extractChords(midiEvents);
    setSong(fileLabel + "  —  chords: " + chords.map(c => c.name).join(" · "), midiEvents, chords);
  }

  // Upload
  fileInput.addEventListener("change", ev => {
    const file = ev.target.files[0];
    if (!file) return;
    file.arrayBuffer().then(ab => {
      try {
        const r = parseMIDI(ab);
        loadNotes(r.notes, file.name.replace(/\.(mid|midi)$/i, ""));
      } catch (e) { alert(e.message); }
    });
  });

  // Sample
  sampleBtn.addEventListener("click", () => {
    try {
      const b64 = window.SAMPLE_MIDI64;
      const bin = atob(b64);
      const ab = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) ab[i] = bin.charCodeAt(i);
      const r = parseMIDI(ab.buffer);
      loadNotes(r.notes, window.SAMPLE_NAME || "sample");
    } catch (e) { alert(e.message); }
  });

  // Playback controls
  playBtn.addEventListener("click", () => {
    if (!chords.length) return;
    if (playing) { playing = false; playBtn.textContent = "▶ Play"; }
    else { playing = true; t0 = performance.now(); playBtn.textContent = "❚❚ Pause"; }
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      const t = nowSeconds();
      let idx = -1;
      for (let i = 0; i < chords.length; i++) {
        if (t >= chords[i].start && t < chords[i].end) { idx = i; break; }
      }
      if (idx !== currentIdx) { currentIdx = idx; renderNow(); }
      if (idx === -1 && t > (chords[chords.length - 1] ? chords[chords.length - 1].end : 0)) {
        playing = false; playBtn.textContent = "▶ Play"; clearInterval(timer);
      }
    }, 120);
  });
  prevBtn.addEventListener("click", () => {
    if (!chords.length) return;
    currentIdx = Math.max(currentIdx - 1, 0);
    accum = chords[currentIdx].start; renderNow();
  });
  nextBtn.addEventListener("click", () => {
    if (!chords.length) return;
    currentIdx = Math.min(currentIdx + 1, chords.length - 1);
    accum = chords[currentIdx].start; renderNow();
  });
  resetBtn.addEventListener("click", () => {
    currentIdx = -1; accum = 0; playing = false; playBtn.textContent = "▶ Play";
    if (timer) { clearInterval(timer); timer = null; }
    renderNow();
  });

  // ---------- full song guide (text + voice) ----------
  function chordLines(co) {
    const lines = [`Now the ${co.name} chord.`];
    for (let sNum = 6; sNum >= 1; sNum--) {
      const fr = co.frets.find(f => f[0] === sNum);
      const muted = co.muted.includes(sNum);
      if (muted) lines.push(`Mute the ${STRING_WORDS[sNum]} string.`);
      else if (fr) lines.push(`Place your ${FINGER_WORDS[fr[2]]} finger on the ${STRING_WORDS[sNum]} string, fret ${fr[1]}.`);
      else lines.push(`Let the ${STRING_WORDS[sNum]} string ring open.`);
    }
    lines.push(co.strum);
    return lines;
  }

  function renderFullGuide() {
    const titleElG = document.getElementById("guideTitle");
    const metaEl = document.getElementById("guideMeta");
    const listEl = document.getElementById("guideList");
    if (!listEl) return;
    const lib = window.guitarbuddy_coach ? window.guitarbuddy_coach.CHORD_COACH : [];
    titleElG.textContent = `How to play ${titleEl.textContent.split(" — ")[0]} — full guide`;
    metaEl.textContent = `${chords.length} section${chords.length === 1 ? "" : "s"} · chords: ${chords.map(c => c.name).join(" → ")}`;
    listEl.innerHTML = "";
    const add = (txt) => { const li = document.createElement("li"); li.innerHTML = txt; listEl.appendChild(li); };
    add(`Get your guitar in tune first — use the <b>Tuner</b> tab. Then we'll learn each of the ${chords.length} chords you need, in the order they appear.`);
    chords.forEach((c, i) => {
      const co = lib.find(x => x.name === c.name);
      if (co) {
        add(`<b>Section ${i + 1} (${c.start.toFixed(1)}s–${c.end.toFixed(1)}s): ${c.name}</b> — ${co.notes}. ` + chordLines(co).slice(1, -1).join(" "));
      } else {
        add(`<b>Section ${i + 1} (${c.start.toFixed(1)}s–${c.end.toFixed(1)}s): ${c.name}</b> — a chord we don't have a step guide for yet; use the notes on the fretboard.`);
      }
    });
    add(`<b>Play it through.</b> Press Play (or the voice guide) and switch chords at the highlighted times. The whole song takes ${chords.length ? chords[chords.length - 1].end.toFixed(0) : 0}s.`);
  }

  function speakFullSong() {
    if (!chords.length || !window.guitarbuddy_coach) return;
    const lib = window.guitarbuddy_coach.CHORD_COACH;
    const songName = (titleEl.textContent.split(" — ")[0] || "this song");
    const items = [];
    items.push({ type: "intro", text: `Full song guide for ${songName}. It uses ${chords.length} chords: ${chords.map(c => c.name).join(", ")}. Let's take it one section at a time.` });
    chords.forEach(c => {
      const co = lib.find(x => x.name === c.name);
      items.push({ type: "chord", name: c.name, lines: co ? chordLines(co) : [`${c.name} chord — not in the step library yet, use the fretboard.`] });
    });
    items.push({ type: "done", text: `Great job. That's the whole song. Try playing it again a little faster!` });

    function run(i) {
      if (i >= items.length) { return; }
      const it = items[i];
      if (it.type === "intro") {
        VOICE.speakSequence([it.text], () => run(i + 1));
      } else if (it.type === "chord") {
        const idx = chords.findIndex(x => x.name === it.name);
        if (idx >= 0) { currentIdx = idx; accum = chords[idx].start; renderNow(); }
        VOICE.speakSequence(it.lines, () => run(i + 1));
      } else {
        VOICE.speak(it.text);
        renderNow();
      }
    }
    run(0);
  }

  document.getElementById("guideFullSong").addEventListener("click", speakFullSong);
  document.getElementById("guideStop").addEventListener("click", () => VOICE.stop());

  // Load the sample on first paint so the page demos instantly
  sampleBtn.click();
});

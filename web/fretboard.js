/* guitar-buddy web: interactive fretboard visualizer. */
"use strict";

const CHORDS = {
  "C":        [0, 4, 7],
  "G":        [7, 11, 2],
  "A minor":  [9, 12, 4],
  "E minor":  [4, 7, 11],
  "D":        [2, 6, 9],
  "A":        [9, 1, 4],
};
const SCALES = {
  "Major pentatonic": [0, 2, 4, 7, 9],
  "Minor pentatonic": [0, 3, 5, 7, 10],
  "Major (Ionian)":   [0, 2, 4, 5, 7, 9, 11],
};

document.addEventListener("DOMContentLoaded", () => {
  const board = document.getElementById("fretboard");
  const NFRETS = 15;

  function buildBoard() {
    board.innerHTML = "";
    const tbl = document.createElement("table");
    tbl.className = "neck";
    const head = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = "string\\fret";
    head.appendChild(corner);
    for (let f = 0; f <= NFRETS; f++) {
      const th = document.createElement("th");
      th.className = f === 0 ? "fret nut" : "fret";
      th.textContent = f;
      head.appendChild(th);
    }
    tbl.appendChild(head);

    for (let r = 0; r < 6; r++) {
      const stringIndex = 5 - r;            // row0 = low E (string6), row5 = high E
      const tr = document.createElement("tr");
      const sh = document.createElement("th");
      sh.className = "str";
      sh.textContent = midiName(OPEN_MIDI[stringIndex]) + `  s${stringIndex + 1}`;
      tr.appendChild(sh);
      for (let f = 0; f <= NFRETS; f++) {
        const midi = OPEN_MIDI[stringIndex] + f;
        const pc = notePitchClass(midi);
        const td = document.createElement("td");
        td.dataset.s = stringIndex;
        td.dataset.f = f;
        td.dataset.midi = midi;
        td.dataset.pc = pc;
        td.className = "cell";
        td.style.setProperty("--pc", TWELVE_COLORS[pc]);
        td.textContent = f === 0 ? midiName(midi) : midiName(midi);
        if ([3, 5, 7, 9, 12].includes(f) && stringIndex === 2) {
          td.classList.add("mark");
        }
        td.addEventListener("click", () => {
          document.querySelectorAll(".cell.sel").forEach(c => c.classList.remove("sel"));
          td.classList.add("sel");
          info.textContent = `${midiName(midi)} = ${midiFreq(midi).toFixed(1)} Hz`
            + `  (string ${stringIndex + 1}, fret ${f})`;
        });
        tr.appendChild(td);
      }
      tbl.appendChild(tr);
    }
    board.appendChild(tbl);
  }

  // ---- highlighting ---------------------------------------------------------
  function clearEnv() {
    document.querySelectorAll(".cell").forEach(c => {
      c.classList.remove("hl", "hl2");
      c.style.removeProperty("background");
      c.style.removeProperty("color");
    });
  }

  function highlightPattern(pairClassSet, cover = true, useColor = true) {
    clearEnv();
    document.querySelectorAll(".cell").forEach(c => {
      if (pairClassSet.has(parseInt(c.dataset.pc))) {
        c.classList.add("hl");
        if (useColor) {
          c.style.background = `var(--pc)`;
          c.style.color = "#121212";
        }
        if (cover) c.classList.add("hl2");
      }
    });
  }

  document.querySelectorAll("[data-highlight]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("on")) {   // click again to turn off
        btn.classList.remove("on");
        clearEnv();
        info.textContent = "Click any note, or pick a chord/scale above.";
        return;
      }
      document.querySelectorAll("[data-highlight]").forEach(x => x.classList.remove("on"));
      btn.classList.add("on");
      const sel = btn.dataset.highlight;
      const def = SCALES[sel] || CHORDS[sel] || null;
      if (def) highlightPattern(new Set(def));
    });
  });
  document.getElementById("clearHl").addEventListener("click", () => {
    clearEnv();
    document.querySelectorAll("[data-highlight]").forEach(x => x.classList.remove("on"));
    info.textContent = "Click any note, or pick a chord/scale above.";
  });

  // voice tour: learn the notes, from the open strings up
  const tourBtn = document.getElementById("notesTour");
  if (tourBtn) tourBtn.addEventListener("click", () => {
    highlightExact([[1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0]], "Open strings: E-A-D-G-B-E (low to high).");
    VOICE.speakSequence([
      "Open strings, from lowest to highest: E, A, D, G, B, E.",
      "String six is the low E. String five is A. String four is D. String three is G. String two is B. String one is the high E.",
      "Each fret raises the note by one half step, so the twelve notes repeat: A, A sharp, B, C, C sharp, D, D sharp, E, F, F sharp, G, G sharp.",
      "Fret twelve is exactly one octave above the open string — the same note name, one octave higher.",
      "Most beginner chords live in the first three frets. Click any note on the board to hear and see where it is.",
    ]);
    if (window.guitarbuddy_fb && window.guitarbuddy_fb.clearEnv) info.textContent = "Open strings: E-A-D-G-B-E.";
  });

  function highlightMidi(m, label) {
    clearEnv();
    positionsForMidi(m).forEach(([s, fx]) => {
      const cell = board.querySelector(`[data-s="${s}"][data-f="${fx}"]`);
      if (cell) cell.classList.add("hl2");
    });
    info.textContent = `${label}: ${midiName(m)} (${midiFreq(m).toFixed(1)} Hz)`;
  }

  // ---- detected notes panel --------------------------------------------------
  const listEl = document.getElementById("noteList");
  const loadEmbedded = () => window.NOTES_DATA ? Promise.resolve(window.NOTES_DATA)
                                              : fetch("notes_data.json").then(r => r.json());
  loadEmbedded()
    .then(data => {
      // clip filter buttons
      const filt = document.getElementById("clipFilter");
      const chips = document.createElement("div");
      chips.className = "chips";
      data.clips.forEach((clip, i) => {
        const b = document.createElement("button");
        b.className = "chip";
        b.textContent = clip.id.replace(/_/g, " ");
        b.dataset.clip = i;
        chips.appendChild(b);
      });
      filt.appendChild(chips);

      const render = (clipIndex) => {
        listEl.innerHTML = "";
        const clip = data.clips[clipIndex === undefined ? undefined : clipIndex];
        if (!clip || !clip.notes.length) {
          const li = document.createElement("li");
          li.textContent = "no notes";
          listEl.appendChild(li);
          return;
        }
        clip.notes.forEach(n => {
          const li = document.createElement("li");
          const btn = document.createElement("button");
          btn.textContent = `${n.name}  ${n.start}s-${n.end}s  ${n.freq}Hz`;
          btn.addEventListener("click", () => highlightMidi(n.midi, `${n.name} @ ${n.start}s`));
          li.appendChild(btn);
          listEl.appendChild(li);
        });
      };
      chips.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => {
        chips.querySelectorAll(".chip").forEach(x => x.classList.remove("active"));
        c.classList.add("active");
        render(parseInt(c.dataset.clip));
      }));
      if (data.clips.length) render(0);
    })
    .catch(() => {
      listEl.innerHTML = "<li>could not load notes_data.json</li>";
    });

  const info = document.getElementById("info");
  info.textContent = "Click any note — or pick a chord/scale above.";
  buildBoard();

  function highlightExact(pairs, label) {
    // pairs: [[stringNum 1..6, fret], ...] highlight exactly those cells
    clearEnv();
    pairs.forEach(([sNum, fx]) => {
      const cell = board.querySelector(`[data-s="${sNum - 1}"][data-f="${fx}"]`);
      if (cell) cell.classList.add("hl2");
    });
    if (label) info.textContent = label;
  }

  // pass highlightMidi/highlightPattern/highlightExact to window for coach pages
  window.guitarbuddy_fb = { highlightMidi, highlightPattern, clearEnv, highlightExact };
});

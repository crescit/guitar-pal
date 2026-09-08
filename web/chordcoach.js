/* guitar-buddy web: chord coach — string-by-string step-by-step guide. */
"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const chipsEl = document.getElementById("chordChips");
  const nameEl = document.getElementById("chordName");
  const notesEl = document.getElementById("chordNotes");
  const diagEl = document.getElementById("chordDiagram");
  const stepsEl = document.getElementById("stepsList");
  const stepLabel = document.getElementById("stepLabel");
  const fb = () => (window.guitarbuddy_fb || {});

  let idx = -1;                 // current step (0-based); -1 = not started
  let sel = null;              // {co, steps, targets}

  function buildSelection(co) {
    const steps = [], targets = [];
    for (let sNum = 6; sNum >= 1; sNum--) {
      const fr = co.frets.find(f => f[0] === sNum);
      const muted = co.muted.includes(sNum);
      if (muted) {
        steps.push(`Don't touch it — mute the ${STRING_WORDS[sNum]} string (${sNum}).`);
        targets.push(null);
      } else if (fr) {
        const midi = OPEN_MIDI[sNum - 1] + fr[1];
        steps.push(`Put your ${FINGER_WORDS[fr[2]]} finger on the ` +
                   `${STRING_WORDS[sNum]} string (${sNum}), fret ${fr[1]}` +
                   ` — that's a ${midiName(midi)}.`);
        targets.push([sNum, fr[1]]);
      } else {
        steps.push(`Let the ${STRING_WORDS[sNum]} string (${sNum}) ring open.`);
        targets.push(null);
      }
    }
    steps.push(co.strum);
    targets.push(null);
    steps.push(`Check it: you're playing ${co.name} — ${co.notes}. ${co.tip || ""}`);
    targets.push(null);
    return { co, steps, targets };
  }

  function renderDiagram(co) {
    diagEl.innerHTML = "";
    const tbl = document.createElement("div");
    tbl.className = "diagram";
    for (let sNum = 6; sNum >= 1; sNum--) {
      const row = document.createElement("div");
      row.className = "drow";
      const lbl = document.createElement("span");
      lbl.className = "dstr";
      lbl.textContent = `${sNum} · ${STRING_WORDS[sNum]}`;
      row.appendChild(lbl);
      const fr = co.frets.find(f => f[0] === sNum);
      const muted = co.muted.includes(sNum);
      const cell = document.createElement("span");
      cell.className = "dcell " + (muted ? "muted" : fr ? "fret" : "open");
      cell.textContent = muted ? "×" : fr ? `${fr[1]} ${FINGER_WORDS[fr[2]][0]}` : "○";
      row.appendChild(cell);
      tbl.appendChild(row);
    }
    diagEl.appendChild(tbl);
  }

  function renderSteps() {
    stepsEl.innerHTML = "";
    sel.steps.forEach((s, i) => {
      const li = document.createElement("li");
      li.textContent = `${i + 1}. ${s}`;
      if (i === idx) li.classList.add("active");
      stepsEl.appendChild(li);
    });
    stepLabel.textContent = idx < 0 ? "Hit Next to start" : `Step ${idx + 1} of ${sel.steps.length}`;
  }

  function highlightTargets() {
    return sel.targets.filter(t => t !== null);
  }

  function showAll() {
    if (!sel) return;
    const t = highlightTargets();
    if (fb().highlightExact) fb().highlightExact(t, `${sel.co.name}: ${sel.co.notes} — press the fingered strings.`);
  }

  function applyStep() {
    renderSteps();
    const tgt = idx >= 0 ? sel.targets[idx] : null;
    if (tgt) {
      if (fb().highlightExact) fb().highlightExact([tgt], `Step ${idx + 1}: ${sel.steps[idx]}`);
    } else if (idx >= 0 && sel.steps[idx].includes("ring open")) {
      showAll();
    }
    if (idx >= 0 && !VOICE.isMuted()) VOICE.speak(sel.steps[idx]);
  }

  document.getElementById("stepSpeak").addEventListener("click", () => {
    if (!sel) return;
    VOICE.speak(sel.steps[Math.max(idx, 0)]);
  });

  function selectChord(co) {
    sel = buildSelection(co);
    idx = -1;
    nameEl.textContent = `${co.name}  ·  ${co.notes}`;
    notesEl.textContent = "";
    renderDiagram(co);
    renderSteps();
    showAll();
  }

  // chord chips
  CHORD_COACH.forEach(co => {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = co.name;
    b.addEventListener("click", () => {
      chipsEl.querySelectorAll(".chip").forEach(x => { x.classList.remove("on"); x.classList.remove("active"); });
      b.classList.add("on");
      selectChord(co);
      const sc = document.getElementById("chordCoach");
      if (sc) sc.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    chipsEl.appendChild(b);
  });

  // default selection = C
  selectChord(CHORD_COACH[0]);

  document.getElementById("stepNext").addEventListener("click", () => {
    if (!sel) return;
    idx = Math.min(idx + 1, sel.steps.length - 1);
    applyStep();
  });
  document.getElementById("stepPrev").addEventListener("click", () => {
    if (!sel) return;
    idx = Math.max(idx - 1, -1);
    applyStep();
  });
  document.getElementById("stepAll").addEventListener("click", showAll);
  document.getElementById("stepReset").addEventListener("click", () => {
    if (!sel) return;
    idx = -1;
    renderSteps();
    showAll();
  });

  // expose so the song coach can drive the step-by-step for a chord
  window.guitarbuddy_coach = { selectChord, CHORD_COACH };
});

/* guitar-buddy web: chord library for the step-by-step coach.
   Fingers follow the Regolin/cowboy conventions. frets = [[stringNum 1..6,
   fret, finger 1=idx..4=pinky]]; muted = strings left open as x; strum
   describes the string target. */
"use strict";

const FINGER_WORDS = { 1: "Index", 2: "Middle", 3: "Ring", 4: "Pinky" };
const STRING_WORDS = { 1: "high E", 2: "B", 3: "G", 4: "D", 5: "A", 6: "low E" };

const CHORD_COACH = [
  {
    name: "C", notes: "C · E · G", pitch: [0, 4, 7],
    frets: [[5, 3, 3], [4, 2, 2], [2, 1, 1]],
    muted: [6],
    strum: "Strum strings 5 → 1. Skip the low E (6).",
    tip: "Keep your wrist relaxed; ring finger on the A string is the farthest out.",
  },
  {
    name: "G", notes: "G · B · D", pitch: [7, 11, 2],
    frets: [[6, 3, 3], [5, 2, 2], [2, 3, 1], [1, 3, 4]],
    muted: [],
    strum: "Strum all six strings.",
    tip: "This is the full G (both E strings fretted at 3). Curl the index to clear the B string.",
  },
  {
    name: "A", notes: "A · C# · E", pitch: [9, 1, 4],
    frets: [[4, 2, 1], [3, 2, 2], [2, 2, 3]],
    muted: [6],
    strum: "Strum 5 → 1. Skip the low E (6).",
    tip: "Three fingers side by side on fret 2 — a tight shape. Watch the D string doesn't ring into the low E.",
  },
  {
    name: "Am", notes: "A · C · E", pitch: [9, 0, 4],
    frets: [[4, 2, 1], [3, 2, 2]],
    muted: [6],
    strum: "Strum 5 → 1. Skip the low E (6).",
    tip: "Same as A but the B string stays open — one finger less to set.",
  },
  {
    name: "E", notes: "E · G# · B", pitch: [4, 8, 11],
    frets: [[5, 2, 2], [4, 2, 3]],
    muted: [],
    strum: "Strum all six strings.",
    tip: "Two fingers on fret 2 of the A and D strings; open strings do the rest.",
  },
  {
    name: "Em", notes: "E · G · B", pitch: [4, 7, 11],
    frets: [[5, 2, 2], [4, 2, 3]],
    muted: [],
    strum: "Strum all six strings.",
    tip: "Same as E but a half-step lower — the G string stays open.",
  },
  {
    name: "D", notes: "D · A · D · F#", pitch: [2, 9, 6],
    frets: [[3, 2, 1], [2, 3, 3], [1, 2, 2]],
    muted: [5, 6],
    strum: "Strum 4 → 1. Skip the low E (6) and A (5).",
    tip: "Play only the four highest strings — keep the top two muted.",
  },
  {
    name: "Dm", notes: "D · A · D · F", pitch: [2, 9, 5],
    frets: [[3, 2, 1], [2, 3, 3], [1, 1, 2]],
    muted: [5, 6],
    strum: "Strum 4 → 1. Skip the low E (6) and A (5).",
    tip: "Same shape as D with the high E lowered to fret 1.",
  },
  {
    name: "A7", notes: "A · C# · E · G", pitch: [9, 1, 4, 7],
    frets: [[4, 2, 1], [2, 2, 2]],
    muted: [6],
    strum: "Strum 5 → 1. Skip the low E (6).",
    tip: "Two fingers on fret 2 — a bluesy open chord.",
  },
];

/* Build step-by-step instructions for a chord, thickest string first. */
function chS(co) { return CHORD_COACH.find(c => c.name === co) || null; }

function buildSteps(co) {
  const steps = [];
  const frets = [...co.frets].reverse(); // stringNum ascending (thin->thick) -> iterate thick->thin below
  // iterate thick (string 6) -> thin (string 1)
  for (let sNum = 6; sNum >= 1; sNum--) {
    const fr = co.frets.find(f => f[0] === sNum);
    const muted = co.muted.includes(sNum);
    const open = !fr && !muted;
    if (muted) {
      steps.push(`Don't touch — mute the ${STRING_WORDS[sNum]} string (${sNum}).`);
    } else if (fr) {
      const midi = OPEN_MIDI[sNum - 1] + fr[1];
      steps.push(`Place your ${FINGER_WORDS[fr[2]]} finger on the ${STRING_WORDS[sNum]} ` +
                 `string (${sNum}), fret ${fr[1]} — that's a ${midiName(midi)}.`);
    } else {
      steps.push(`Let the ${STRING_WORDS[sNum]} string (${sNum}) ring open.`);
    }
  }
  steps.push(co.strum);
  steps.push(`Check it: you're playing ${co.name} — ${co.notes}. ${co.tip || ""}`);
  return steps;
}

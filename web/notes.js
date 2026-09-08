/* guitar-buddy web: shared note utilities. */
const NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const OPEN_MIDI = [64, 59, 55, 50, 45, 40];   // string 1 (high E) -> 6 (low E)

function midiName(m) {
  m = Math.round(m);
  return NOTE_NAMES[((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);
}
function midiFreq(m) { return 440 * Math.pow(2, (m - 69) / 12); }
function centsBetween(freq, targetMidi) {
  return 1200 * Math.log2(freq / midiFreq(targetMidi));
}
function notePitchClass(m) { return ((Math.round(m) % 12) + 12) % 12; }

/* note -> fretboard positions [(string, fret)] on the rendered neck */
function positionsForMidi(m, maxFret = 15) {
  const out = [];
  for (let s = 0; s < 6; s++) {
    for (let f = 0; f <= maxFret; f++) {
      if (OPEN_MIDI[s] + f === Math.round(m)) out.push([s, f]);
    }
  }
  return out;
}

const TWELVE_COLORS = [
  "#e74c3c","#e67e22","#f1c40f","#7dbb2e","#27ae60","#16a085",
  "#27a7b5","#2980b9","#5b6fd0","#8e44ad","#c0392b","#b0603a",
];

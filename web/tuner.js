/* guitar-buddy web: guitar tuner (mic pitch detection). */
"use strict";

const TUNING = [
  { label: "E2 (6th)", midi: 40 },
  { label: "A2 (5th)", midi: 45 },
  { label: "D3 (4th)", midi: 50 },
  { label: "G3 (3rd)", midi: 55 },
  { label: "B3 (2nd)", midi: 59 },
  { label: "E4 (1st)", midi: 64 },
];

let ctx = null, analyser = null, dataBuf = null;
let running = false;

const el = {
  status: document.getElementById("tunerStatus"),
  note: document.getElementById("detectedNote"),
  freq: document.getElementById("detectedFreq"),
  needle: document.getElementById("needle"),
  centsLabel: document.getElementById("centsLabel"),
  targetLabel: document.getElementById("targetLabel"),
  stringSelect: document.getElementById("stringSelect"),
  dot: document.getElementById("dot"),
};

function detectPitch(buf, sr) {
  const len = buf.length;
  const rms = Math.sqrt(buf.reduce((a, v) => a + v * v, 0) / len);
  if (rms < 0.01) return null;             // too quiet
  const minLag = Math.floor(sr / 1200);
  const maxLag = Math.floor(sr / 55);
  let best = -1, bestLag = -1, bestNorm = 0;
  for (let lag = minLag; lag < maxLag; lag++) {
    let num = 0, denA = 0, denB = 0;
    for (let i = 0; i + lag < len; i++) {
      num += buf[i] * buf[i + lag];
      denA += buf[i] * buf[i];
      denB += buf[i + lag] * buf[i + lag];
    }
    const corr = num / Math.sqrt(denA * denB || 1e-12);   // normalized
    if (corr > bestNorm) { bestNorm = corr; bestLag = lag; best = corr; }
  }
  if (bestLag < 0 || bestNorm < 0.6) return null;          // not periodic enough
  return sr / bestLag;
}

function centsSharpFreq(freq) {
  if (!freq) return null;
  const midi = 69 + 12 * Math.log2(freq / 440);
  return midi;
}

function setNeedle(cents, inTune) {
  const mid = el.needle.clientWidth / 2;
  const maxC = 50;
  const clamped = Math.max(-maxC, Math.min(maxC, cents));
  const frac = clamped / maxC;
  el.needle.style.transform = `translateX(${frac * mid}px)`;
  el.centsLabel.textContent = (cents >= 0 ? "+" : "") + cents.toFixed(0) + " cents";
  el.centsLabel.style.color = inTune ? "#2ecc71" : (Math.abs(cents) > 25 ? "#e74c3c" : "#f1c40f");
  el.dot.style.background = inTune ? "#2ecc71" : "#e74c3c";
}

function tick() {
  if (!running) return;
  analyser.getFloatTimeDomainData(dataBuf);
  const freq = detectPitch(dataBuf, ctx.sampleRate);
  if (!freq) {
    el.note.textContent = "?";
    el.freq.textContent = "-";
    el.centsLabel.textContent = "no pitch";
    requestAnimationFrame(tick);
    return;
  }
  const midiCtr = centsSharpFreq(freq);
  const name = midiName(midiCtr);
  const nearest = Math.round(midiCtr);
  const cents = 1200 * Math.log2(freq / midiFreq(nearest));
  el.note.textContent = name;
  el.freq.textContent = freq.toFixed(1) + " Hz";

  const targetMidi = parseInt(el.stringSelect.value, 10);
  const targetCents = 1200 * Math.log2(freq / midiFreq(targetMidi));
  setNeedle(targetCents, Math.abs(targetCents) < 5);
  el.targetLabel.textContent = "tuning " + midiName(targetMidi);
  requestAnimationFrame(tick);
}

async function start() {
  if (running) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    const src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 4096;
    analyser.smoothingTimeConstant = 0.6;
    dataBuf = new Float32Array(analyser.fftSize);
    src.connect(analyser);
    running = true;
    el.status.textContent = "listening...";
    tick();
  } catch (e) {
    el.status.textContent = "mic error: " + e.message +
      " (grant mic permission; Safari needs the icon turned on)";
  }
}

function stop() {
  running = false;
  el.status.textContent = "stopped";
}

function fillStrings() {
  TUNING.forEach(t => {
    const o = document.createElement("option");
    o.value = t.midi;
    o.textContent = t.label;
    el.stringSelect.appendChild(o);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  fillStrings();
  document.getElementById("tunerOn").addEventListener("click", start);
  document.getElementById("tunerOff").addEventListener("click", stop);
  // reference tone buttons
  TUNING.forEach((t, i) => {
    const btn = document.getElementById("ref" + i);
    if (!btn) return;
    btn.addEventListener("click", () => {
      const osc = ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      osc.resume();
      const o = osc.createOscillator(), g = osc.createGain();
      o.frequency.value = midiFreq(t.midi);
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, osc.currentTime);
      g.gain.exponentialRampToValueAtTime(0.3, osc.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, osc.currentTime + 1.2);
      o.connect(g).connect(osc.destination);
      o.start();
      o.stop(osc.currentTime + 1.3);
    });
  });
});

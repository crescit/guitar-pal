/* guitar-buddy web: guided voice narration (Web Speech API).
   Reads the coaching out loud so you can keep your eyes on the guitar. */
"use strict";

const VOICE = (function () {
  let muted = false;
  try { muted = localStorage.getItem("gb-voice") === "off"; } catch (e) {}
  let voice = null;

  function pick() {
    if (typeof speechSynthesis === "undefined") return;
    const vs = speechSynthesis.getVoices();
    voice = vs.find(v => /^en[_ -]?US/i.test(v.lang || "")) ||
            vs.find(v => /^en/i.test(v.lang || "")) || null;
  }
  if (typeof speechSynthesis !== "undefined") {
    pick();
    speechSynthesis.onvoiceschanged = pick;
  }

  function speak(text) {
    if (muted || typeof speechSynthesis === "undefined" || !text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US"; u.rate = 0.95; u.pitch = 1;
    if (voice) u.voice = voice;
    speechSynthesis.speak(u);
  }

  /* Speak a sequence of lines one after another. */
  function speakSequence(lines, done) {
    if (muted || typeof speechSynthesis === "undefined" || !lines.length) {
      if (done) done(); return;
    }
    speechSynthesis.cancel();
    let i = 0;
    const next = () => {
      if (i >= lines.length) { if (done) done(); return; }
      const text = lines[i++];
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US"; u.rate = 0.95; u.pitch = 1;
      if (voice) u.voice = voice;
      let fired = false;
      const finish = () => { if (!fired) { fired = true; clearTimeout(timer); next(); } };
      u.onend = finish;
      // safety: advance even if onend never fires (headless/audio-less browsers)
      const timer = setTimeout(finish, Math.max(1800, text.length * 90));
      speechSynthesis.speak(u);
    };
    next();
  }

  function stop() { if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel(); }

  function toggle() {
    muted = !muted;
    try { localStorage.setItem("gb-voice", muted ? "off" : "on"); } catch (e) {}
    if (muted) stop(); else speak("Voice guide on.");
    return !muted;
  }
  function isMuted() { return muted; }

  // wire the topbar voice button if present
  document.addEventListener("DOMContentLoaded", () => {
    const b = document.getElementById("voiceBtn");
    if (b) {
      b.textContent = muted ? "🔇" : "🔊";
      b.title = muted ? "Voice guide off — click to turn on" : "Voice guide on — click to mute";
      b.addEventListener("click", () => {
        const on = toggle();
        b.textContent = on ? "🔊" : "🔇";
        b.title = on ? "Voice guide on — click to mute" : "Voice guide off — click to turn on";
      });
    }
  });

  return { speak, speakSequence, stop, toggle, isMuted };
})();

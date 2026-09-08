/* guitar-buddy web: guided voice narration.
   Prefers native macOS speech synthesis (backend /api/tts via `say`, so you
   get real Apple voices — Samantha, Daniel, etc.) and falls back to the Web
   Speech API when the backend isn't running. */
"use strict";

const VOICE = (function () {
  let muted = false;
  try { muted = localStorage.getItem("gb-voice") === "off"; } catch (e) {}
  let voice = "Samantha";          // native `say` voice name
  let native = null;               // 'yes' | 'no' | null (unknown, probe once)
  let nativeBusy = false;
  const queue = [];

  /* Probe the backend once so we know whether native TTS is available. */
  function probe() {
    if (native !== null) return Promise.resolve(native === "yes");
    return fetch("/api/voices")
      .then(r => { native = r.ok ? "yes" : "no"; return r.ok; })
      .catch(() => { native = "no"; return false; });
  }

  function speakNative(text, done) {
    fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice }),
    })
      .then(r => { if (!r.ok) throw new Error("tts failed"); return r.blob(); })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = new Audio(url);
        a.onended = () => { URL.revokeObjectURL(url); if (done) done(); };
        a.onerror = () => { URL.revokeObjectURL(url); if (done) done(); };
        a.play().catch(() => { if (done) done(); });
      })
      .catch(() => { if (done) done(); });
  }

  function speakWeb(text) {
    if (typeof speechSynthesis === "undefined") return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US"; u.rate = 1; u.pitch = 1;
    const vs = speechSynthesis.getVoices();
    const v = vs.find(x => /^en[_ -]?US/i.test(x.lang || "")) ||
              vs.find(x => /^en/i.test(x.lang || "")) || null;
    if (v) u.voice = v;
    speechSynthesis.speak(u);
  }

  function speak(text) {
    if (muted || !text) return;
    probe().then(ok => {
      if (ok) speakNative(text);
      else speakWeb(text);
    });
  }

  /* Speak lines one after another. */
  function speakSequence(lines, done) {
    if (muted || !lines.length) { if (done) done(); return; }
    probe().then(ok => {
      if (!ok) { webSequence(lines, done); return; }
      queue.length = 0; queue.push(...lines);
      let i = 0;
      nativeBusy = false;
      const next = () => {
        if (i >= queue.length) { if (done) done(); return; }
        nativeBusy = true;
        speakNative(queue[i++], () => {
          nativeBusy = false;
          next();
        });
      };
      next();
    });
  }

  function webSequence(lines, done) {
    if (typeof speechSynthesis === "undefined") { if (done) done(); return; }
    speechSynthesis.cancel();
    let i = 0;
    const next = () => {
      if (i >= lines.length) { if (done) done(); return; }
      const u = new SpeechSynthesisUtterance(lines[i++]);
      u.lang = "en-US"; u.rate = 1; u.pitch = 1;
      const vs = speechSynthesis.getVoices();
      const v = vs.find(x => /^en[_ -]?US/i.test(x.lang || "")) || null;
      if (v) u.voice = v;
      let fired = false;
      const finish = () => { if (!fired) { fired = true; clearTimeout(timer); next(); } };
      u.onend = finish;
      const timer = setTimeout(finish, Math.max(1800, lines.length * 90));
      speechSynthesis.speak(u);
    };
    next();
  }

  function stop() {
    queue.length = 0;
    if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
  }

  function toggle() {
    muted = !muted;
    try { localStorage.setItem("gb-voice", muted ? "off" : "on"); } catch (e) {}
    if (muted) stop(); else speak("Voice guide on.");
    return !muted;
  }
  function isMuted() { return muted; }

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

/* guitar-buddy web: live detection demo (webcam + video upload). */
"use strict";

const Live = (function () {
  let mode = "webcam";
  let stream = null;
  let timer = null;
  let pending = false;

  const $ = id => document.getElementById(id);

  // ---- backend ---------------------------------------------------------
  function backend() {
    return fetch("/api/health").then(r => r.ok).catch(() => false);
  }

  // ---- webcam ----------------------------------------------------------
  async function startWebcam() {
    const status = $("wcStatus");
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: "environment" },
        audio: false,
      });
    } catch (e) {
      status.textContent = "Camera denied or unavailable — check browser permission.";
      return;
    }
    $("wcPlaceholder").hidden = true;
    $("wcFrame").hidden = false;
    $("wcStart").disabled = true;
    $("wcStop").disabled = false;
    status.textContent = "Live. Point a guitar at the camera.";
    const video = document.createElement("video");
    video.srcObject = stream;
    video.play();
    const canvas = document.createElement("canvas");
    canvas.width = 1280; canvas.height = 720;
    const ctx = canvas.getContext("2d");
    timer = setInterval(() => {
      if (pending) return;
      pending = true;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const image = canvas.toDataURL("image/jpeg", 0.7);
      fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image, with_hands: true }),
      })
        .then(r => r.json())
        .then(res => renderFrame(res))
        .catch(() => { /* backend hiccup — keep trying */ })
        .finally(() => { pending = false; });
    }, 180);
  }

  function renderFrame(res) {
    if (res.error) return;
    $("wcFrame").src = "data:image/jpeg;base64," + res.frame;
    const neck = $("wcNeck"), neckEmpty = $("wcNeckEmpty");
    if (res.neck) {
      neck.src = "data:image/jpeg;base64," + res.neck;
      neck.hidden = false;
      neckEmpty.hidden = true;
    } else {
      neck.hidden = true;
      neckEmpty.hidden = false;
    }
    $("wcStatus").textContent = res.guitar
      ? `Guitar confirmed (${Math.round((res.guitar_confidence || 0) * 100)}%).`
      : "Looking for a guitar and neck…";
    renderNotes($("wcNotes"), res.fingers || []);
  }

  function stopWebcam() {
    if (timer) { clearInterval(timer); timer = null; }
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    $("wcStart").disabled = false;
    $("wcStop").disabled = true;
    $("wcFrame").src = "";
    $("wcPlaceholder").hidden = false;
    $("wcFrame").hidden = true;
    $("wcStatus").textContent = "Stopped.";
  }

  // ---- video ------------------------------------------------------------
  async function analyzeVideo() {
    const file = $("vdFile").files[0];
    if (!file) { $("vdStatus").textContent = "Choose a video file first."; return; }
    $("vdGo").disabled = true;
    $("vdStatus").textContent = "Uploading and analyzing… (this can take a moment)";
    const fd = new FormData();
    fd.append("file", file);
    try {
      const resp = await fetch("/api/video", { method: "POST", body: fd });
      const res = await resp.json();
      if (res.error) throw new Error(res.error);
      $("vdPlayer").src = res.url;
      $("vdPlayer").hidden = false;
      $("vdPlayer").play();
      $("vdStatus").textContent =
        `Done — ${res.frames_processed} frames in ${res.elapsed}s.`;
      renderTimeline($("vdNotes"), res.timeline || []);
    } catch (e) {
      $("vdStatus").textContent = "Analysis failed: " + e.message;
    } finally {
      $("vdGo").disabled = false;
    }
  }

  function renderTimeline(el, timeline) {
    el.innerHTML = "";
    if (!timeline.length) {
      el.innerHTML = "<li>No notes detected in this clip.</li>";
      return;
    }
    for (const n of timeline) {
      const li = document.createElement("li");
      li.textContent = `${n.note}  ${n.start.toFixed(2)}s–${n.end.toFixed(2)}s  (×${n.count})`;
      el.appendChild(li);
    }
  }

  function renderNotes(el, fingers) {
    el.innerHTML = "";
    if (!fingers.length) {
      el.innerHTML = "<li>No fingertips detected.</li>";
      return;
    }
    for (const f of fingers) {
      const li = document.createElement("li");
      li.textContent = f.note
        ? `${f.note}  string ${f.string + 1}  fret ${f.fret}  (conf ${f.conf.toFixed(2)})`
        : `finger (conf ${f.conf.toFixed(2)})`;
      el.appendChild(li);
    }
  }

  // ---- wiring ------------------------------------------------------------
  function setMode(m) {
    mode = m;
    $("webcamPanel").hidden = m !== "webcam";
    $("videoPanel").hidden = m !== "video";
    document.querySelectorAll("#modeChips .chip").forEach(c => {
      c.classList.toggle("active", c.dataset.mode === m);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("wcStart").addEventListener("click", startWebcam);
    $("wcStop").addEventListener("click", stopWebcam);
    $("vdGo").addEventListener("click", analyzeVideo);
    document.querySelectorAll("#modeChips .chip").forEach(c => {
      c.addEventListener("click", () => setMode(c.dataset.mode));
    });
    backend().then(ok => {
      $("backendStatus").textContent = ok
        ? "Backend online — detection is live."
        : "Backend offline. Run make up to start it.";
      $("backendHint").hidden = ok;
    });
  });

  return { stopWebcam };
})();

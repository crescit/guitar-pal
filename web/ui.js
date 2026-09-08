/* guitar-buddy web: shared chrome (topbar theme toggle, active nav). */
(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("gb-theme");
  if (saved === "dark") root.dataset.theme = "dark";
  const btn = document.getElementById("themeBtn");
  function renderBtn() {
    if (btn) btn.textContent = root.dataset.theme === "dark" ? "☀️" : "🌙";
  }
  if (btn) {
    renderBtn();
    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "" : "dark";
      root.dataset.theme = next;
      localStorage.setItem("gb-theme", next);
      renderBtn();
    });
  }
  // mark the active nav link
  const here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-link").forEach(function (a) {
    if (a.getAttribute("href") === here) a.classList.add("active");
  });
})();

function nowPlaying() { /* hook for future live feedback */ }

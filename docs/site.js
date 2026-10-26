/* Devices Simulator product page — small progressive enhancements only.
   Core navigation, downloads and FAQs work without JavaScript. */
(() => {
  "use strict";
  const links = [...document.querySelectorAll(".download-options > a[data-os]")];
  const hint = document.getElementById("os-recommendation");
  const agent = (navigator.userAgent || "").toLowerCase();
  let preferred = null;
  if (/windows/.test(agent)) preferred = "windows";
  else if (/macintosh|mac os x/.test(agent)) preferred = "macos";
  else if (/linux/.test(agent) && !/android/.test(agent)) preferred = "linux";

  links.forEach(link => {
    const isMatch = preferred === "macos" ? link.dataset.os?.startsWith("macos-") : link.dataset.os === preferred;
    if (isMatch) link.classList.add("recommended");
  });
  if (hint && preferred === "windows") {
    hint.textContent = "Windows detected. Choose the Windows x64 ZIP, or select another platform below.";
  } else if (hint && preferred === "linux") {
    hint.textContent = "Linux detected. Choose the Linux x64 archive, or select another platform below.";
  } else if (hint && preferred === "macos") {
    hint.textContent = "Mac detected. Select Apple Silicon for M-series Macs, or Intel for older Macs.";
  }

  const menu = document.querySelector(".mobile-menu");
  if (menu) {
    menu.querySelectorAll("nav a").forEach(link => {
      link.addEventListener("click", () => { menu.open = false; });
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && menu.open) {
        menu.open = false;
        menu.querySelector("summary")?.focus();
      }
    });
    document.addEventListener("click", event => {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
  }
})();

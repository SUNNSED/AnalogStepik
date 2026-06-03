const container = document.getElementById("holo-container");

if (!container) {
  throw new Error("holo-container not found");
}

container.classList.add("holo-container");
container.innerHTML = `
  <div class="holo-card" aria-label="GUAP hologram">
    <div class="holo-face holo-face-front">
      <div class="holo-mark">
        <img src="./guap-outline.png" alt="GUAP" class="holo-img holo-cyan" />
        <img src="./guap-outline.png" alt="" class="holo-img holo-red" aria-hidden="true" />
      </div>
    </div>
    <div class="holo-face holo-face-back" aria-hidden="true">
      <div class="holo-mark">
        <img src="./guap-outline.png" alt="" class="holo-img holo-cyan" />
        <img src="./guap-outline.png" alt="" class="holo-img holo-red" />
      </div>
    </div>
  </div>
`;

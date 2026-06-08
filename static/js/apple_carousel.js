(function () {
  function initAppleCarousels() {
    document.querySelectorAll("[data-apple-carousel]").forEach((carousel) => {
      if (carousel.dataset.carouselInited === "1") return;
      carousel.dataset.carouselInited = "1";

      const track = carousel.querySelector("[data-carousel-track]");
      if (!track) return;

      const slides = Array.from(track.children);
      const dots = Array.from(carousel.querySelectorAll("[data-carousel-dot]"));
      const prev = carousel.querySelector("[data-carousel-prev]");
      const next = carousel.querySelector("[data-carousel-next]");
      let index = 0;

      function render() {
        track.style.transform = "translate3d(" + -index * 100 + "%, 0, 0)";
        dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
      }
      function move(step) {
        if (!slides.length) return;
        index = (index + step + slides.length) % slides.length;
        render();
      }
      function goTo(i) {
        index = i;
        render();
      }

      if (prev) prev.addEventListener("click", () => move(-1));
      if (next) next.addEventListener("click", () => move(1));
      dots.forEach((dot, i) => dot.addEventListener("click", () => goTo(i)));

      let touchStartX = 0;
      let touchStartY = 0;
      track.addEventListener(
        "touchstart",
        (ev) => {
          const t = ev.changedTouches[0];
          touchStartX = t.clientX;
          touchStartY = t.clientY;
        },
        { passive: true }
      );
      track.addEventListener(
        "touchend",
        (ev) => {
          const t = ev.changedTouches[0];
          const dx = t.clientX - touchStartX;
          const dy = t.clientY - touchStartY;
          if (Math.abs(dx) < 42 || Math.abs(dx) < Math.abs(dy)) return;
          move(dx < 0 ? 1 : -1);
        },
        { passive: true }
      );

      render();
    });
  }

  window.initAppleCarousels = initAppleCarousels;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAppleCarousels, { once: true });
  } else {
    initAppleCarousels();
  }
  window.addEventListener("load", initAppleCarousels);
})();

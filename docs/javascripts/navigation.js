// Material uses checkboxes for its responsive navigation and search panels.
function connectPanel(id, panel, breakpoint) {
  const toggle = document.getElementById(id);
  const trigger = document.querySelector(`.md-header label[for="${id}"]`);
  if (!panel || !toggle || !trigger) return;

  const desktop = window.matchMedia(breakpoint);
  panel.id = id + "-panel";
  trigger.setAttribute("aria-controls", panel.id);
  function update() {
    panel.inert = !desktop.matches && !toggle.checked;
    trigger.setAttribute("aria-expanded", String(toggle.checked));
  }

  trigger.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!event.repeat) trigger.click();
    } else if (event.key === " ") {
      event.preventDefault();
    }
  });
  trigger.addEventListener("keyup", event => {
    if (event.key === " ") {
      event.preventDefault();
      trigger.click();
    }
  });

  if (id === "__drawer") {
    const close = document.createElement("button");
    close.type = "button";
    close.className = "meldh-close-menu";
    close.textContent = "Close menu";
    panel.querySelector(".md-nav__title").after(close);
    close.addEventListener("click", () => toggle.click());
    document.addEventListener("keydown", event => {
      if (desktop.matches || !toggle.checked) return;
      if (event.key === "Escape") {
        event.preventDefault();
        toggle.click();
      }
      if (event.key === "Tab") {
        const links = [...panel.querySelectorAll("a[href], button")].filter(el => el.getClientRects().length);
        const first = links[0], last = links[links.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });
  }

  toggle.addEventListener("change", () => {
    update();
    if (desktop.matches) return;
    if (!toggle.checked) {
      trigger.focus({ preventScroll: true });
    } else if (id === "__drawer") {
      panel.querySelector(".meldh-close-menu").focus({ preventScroll: true });
    } else {
      panel.querySelector("input[type=text]").focus({ preventScroll: true });
    }
  });
  desktop.addEventListener("change", () => {
    if (desktop.matches && toggle.checked) toggle.click();
    update();
  });
  window.addEventListener("pageshow", update);
  update();
}

connectPanel("__drawer", document.querySelector(".md-sidebar--primary"), "(min-width: 76.25em)");
connectPanel("__search", document.querySelector(".md-search"), "(min-width: 60em)");

// Skipping the header is a focus change. Keep it out of the theme's
// fragment-navigation routine, which also closes an open drawer.
const skip = document.querySelector(".md-skip");
if (!document.getElementById("main-content")) {
  const article = document.querySelector("main article.md-content__inner");
  if (article) {
    article.id = "main-content";
    article.tabIndex = -1;
  }
}
if (skip) skip.hash = "main-content";
skip?.addEventListener("click", event => {
  const content = document.getElementById("main-content");
  if (content) {
    event.preventDefault();
    content.focus({ preventScroll: true });
    content.scrollIntoView({ block: "start" });
  }
});

// The theme listens to keyup for queries. Include paste, autofill and dictation.
document.querySelector(".md-search__input")?.addEventListener("input", event => {
  event.target.dispatchEvent(new Event("keyup"));
});

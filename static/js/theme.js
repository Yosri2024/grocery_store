/* Grocery Store — night mode (vanilla JS, Alpine-compatible).
 * Strategy: <html class="dark"> + localStorage "grocery-theme".
 * - "dark" / "light" persisted
 * - default: prefers-color-scheme
 * - synced across tabs via `storage` event
 */
(function () {
  var KEY = "grocery-theme";

  function getStored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function setStored(value) {
    try {
      localStorage.setItem(KEY, value);
    } catch (e) { /* private mode: ignore */ }
  }

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function apply(dark) {
    document.documentElement.classList.toggle("dark", dark);
    syncButtons(dark);
  }

  function syncButtons(dark) {
    document.querySelectorAll("[data-theme-icon-moon]").forEach(function (el) {
      el.classList.toggle("hidden", dark);
    });
    document.querySelectorAll("[data-theme-icon-sun]").forEach(function (el) {
      el.classList.toggle("hidden", !dark);
    });
    document.querySelectorAll("[data-theme-toggle]").forEach(function (el) {
      el.setAttribute("aria-pressed", dark ? "true" : "false");
      el.setAttribute("title", dark ? "Passer en mode jour" : "Passer en mode nuit");
    });
  }

  window.toggleTheme = function () {
    var dark = !isDark();
    apply(dark);
    setStored(dark ? "dark" : "light");
  };

  // Apply ASAP on every page (the <head> inline snippet already did it;
  // this re-syncs icons after DOM parse).
  document.addEventListener("DOMContentLoaded", function () {
    syncButtons(isDark());
  });

  // Keep multiple tabs in sync.
  window.addEventListener("storage", function (e) {
    if (e.key === KEY) {
      apply(e.newValue === "dark");
    }
  });
})();

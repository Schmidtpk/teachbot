// IID-UI-CONTENT-VIEW, IID-UI-CONTENT-MARK
// Loaded on every page as Chainlit's custom_js (.chainlit/config.toml). Does nothing unless
// the server says the current course has viewer documents (app.py `on_chat_start`).
//
//  * a header button that opens/closes the viewer panel (on phones: switches to it and back);
//  * opens the panel by itself on wide screens, unless the student closed it with the button;
//  * clicks on viewer links in answers open the page in the panel instead of a new tab.
//
// All requests go to the server as window messages (Chainlit forwards them to
// `on_window_message`), because only the server can open Chainlit's element sidebar.
(function () {
  "use strict";
  var ORIGIN = window.location.origin;
  var PREF_KEY = "lectos_viewer_pref"; // "closed" once the student closes it via the button
  var available = 0;

  function post(msg) { window.postMessage(msg, ORIGIN); }
  function isOpen() { return !!document.getElementById("lectos-viewer"); }
  function narrow() { return window.matchMedia("(max-width: 767px)").matches; }
  function getPref() { try { return localStorage.getItem(PREF_KEY); } catch (e) { return null; } }
  function setPref(v) { try { localStorage.setItem(PREF_KEY, v); } catch (e) { /* private mode */ } }

  function label() {
    if (isOpen()) return narrow() ? "💬 Chat" : "📖 Hide slides";
    return "📖 Slides";
  }

  // Keep the button in Chainlit's header, which React re-renders at will.
  function ensureButton() {
    var btn = document.getElementById("lectos-viewer-button");
    if (!available) {
      if (btn) btn.remove();
      return;
    }
    var anchor = document.getElementById("theme-toggle") || document.getElementById("readme-button");
    var header = document.getElementById("header");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "lectos-viewer-button";
      btn.type = "button";
      btn.className = "lectos-viewer-header-btn";
      btn.addEventListener("click", function () {
        if (isOpen()) { setPref("closed"); post({ type: "lectos_viewer_close" }); }
        else { setPref("open"); post({ type: "lectos_viewer_open" }); }
      });
    }
    if (!btn.isConnected) {
      if (anchor && anchor.parentElement) anchor.parentElement.insertBefore(btn, anchor);
      else if (header) header.appendChild(btn);
      else return;
    }
    var text = label();
    if (btn.textContent !== text) btn.textContent = text;
  }

  new MutationObserver(ensureButton).observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener("message", function (e) {
    if (e.source !== window || !e.data || e.data.type !== "lectos_viewer_available") return;
    available = Number(e.data.count) || 0;
    ensureButton();
    if (available && !narrow() && getPref() !== "closed" && !isOpen()) post({ type: "lectos_viewer_open" });
  });

  // IID-UI-CONTENT-MARK: answer links (rewritten by the server to /viewer/...) open in the
  // panel. Ctrl/Cmd/Shift/middle click keep the browser default (new tab / window).
  document.addEventListener("click", function (e) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a || a.closest("#lectos-viewer")) return;
    var url;
    try { url = new URL(a.getAttribute("href"), window.location.href); } catch (err) { return; }
    if (url.origin !== ORIGIN || url.pathname.indexOf("/viewer/") !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    post({ type: "lectos_viewer_open", href: decodeURIComponent(url.pathname) + url.hash });
  }, true);
})();

// IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK
// Viewer panel in Chainlit's element sidebar: a document picker and the course's HTML in a
// same-origin iframe (served by /viewer/<course>/<file>, see app.py).
//
// Props (from app.py `_open_viewer`): docs = [{id, label, url}], start = url[#fragment].
//
// It reports where the student is by posting {type: "lectos_viewer_state", ...} to its own
// window; Chainlit forwards window messages to the server (`on_window_message`). The
// location is read by polling, which works the same for reveal.js decks (current slide id),
// the card viewer (#card-id) and any other page (#anchor) without hooking into each one.
import { useEffect, useRef, useState } from "react";

const POLL_MS = 400;

export default function HtmlViewer() {
  const docs = props.docs || [];
  const frame = useRef(null);
  const lastKey = useRef("");
  const [initialSrc] = useState(props.start || (docs[0] ? docs[0].url : ""));
  const [current, setCurrent] = useState({ doc: "", href: initialSrc });

  const post = (msg) => window.postMessage(msg, window.location.origin);

  // Where is the iframe now? Same origin, so its window can be read directly.
  const locate = () => {
    try {
      const w = frame.current && frame.current.contentWindow;
      if (!w) return null;
      const path = decodeURIComponent(w.location.pathname);
      const doc = docs.find((d) => d.url === path);
      if (!doc) return null;
      let loc = "";
      if (w.Reveal && typeof w.Reveal.getCurrentSlide === "function") {
        const slide = w.Reveal.getCurrentSlide();
        loc = (slide && slide.id) || "";
      } else {
        loc = decodeURIComponent((w.location.hash || "").replace(/^#\/?/, ""));
      }
      return { doc: doc.id, loc, href: path + w.location.hash };
    } catch (e) {
      return null; // page still loading
    }
  };

  // IID-UI-CONTENT-CONTEXT: report location changes; report "closed" when unmounted
  // (Chainlit's close button, swiping the mobile sheet away, or a new chat).
  useEffect(() => {
    const tick = () => {
      const here = locate();
      if (!here) return;
      const key = here.doc + "#" + here.loc;
      if (key === lastKey.current) return;
      lastKey.current = key;
      setCurrent({ doc: here.doc, href: here.href });
      post({ type: "lectos_viewer_state", open: true, doc: here.doc, loc: here.loc });
    };
    const timer = setInterval(tick, POLL_MS);
    tick();
    return () => {
      clearInterval(timer);
      post({ type: "lectos_viewer_state", open: false });
    };
  }, []);

  // IID-UI-CONTENT-MARK: go to a page — same document: change only the fragment (no reload
  // of a 7 MB deck); other document: load it.
  const go = (href) => {
    const [path, hash] = href.split("#");
    try {
      const w = frame.current.contentWindow;
      if (decodeURIComponent(w.location.pathname) === path) {
        w.location.hash = hash ? "#" + hash : "";
        return;
      }
    } catch (e) {
      /* not loaded yet: fall through and load it */
    }
    frame.current.src = href;
  };

  // A click on a viewer link in an answer (public/viewer.js) while the panel is open.
  // Only messages from this window: the iframe's own postMessages are not commands.
  useEffect(() => {
    const onMessage = (e) => {
      if (e.source !== window || !e.data || e.data.type !== "lectos_viewer_open") return;
      if (typeof e.data.href === "string" && e.data.href.startsWith("/viewer/")) go(e.data.href);
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <div id="lectos-viewer" className="lectos-viewer">
      <div className="lectos-viewer-bar">
        <select
          className="lectos-viewer-select"
          aria-label="Document"
          value={current.doc || (docs[0] ? docs[0].id : "")}
          onChange={(e) => {
            const d = docs.find((x) => x.id === e.target.value);
            if (d) go(d.url);
          }}
        >
          {docs.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
        <a
          className="lectos-viewer-btn"
          href={current.href}
          target="_blank"
          rel="noopener"
          title="Open in a new tab"
        >
          ↗
        </a>
        <button
          className="lectos-viewer-btn lectos-viewer-to-chat"
          onClick={() => post({ type: "lectos_viewer_close" })}
          title="Back to the chat"
        >
          💬 Chat
        </button>
      </div>
      <iframe
        ref={frame}
        className="lectos-viewer-frame"
        src={initialSrc}
        title="Lecture material"
      />
    </div>
  );
}

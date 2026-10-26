import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { initSentry } from "./sentry";

initSentry();
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// PWA (Faz 2): service worker — telefona "ana ekrana ekle" ile kurulabilir.
// http (LAN) ve https (relay/domains) protokollerinde kaydolur; file:// hariç.
if (
  "serviceWorker" in navigator &&
  (location.protocol === "http:" || location.protocol === "https:")
) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* SW kurulamadı — uygulama normal çalışmayı sürdürür */
    });
  });
}

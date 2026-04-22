import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { initSentry } from "./sentry";

// Init Sentry cât mai devreme — nainte să rendăm App, ca erorile de render
// timpuriu să fie captate. No-op dacă VITE_SENTRY_DSN nu e setat.
initSentry();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

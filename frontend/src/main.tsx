import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import "./index.css";
import "./styles/motion.css";
import "./styles/shell.css";
import "./styles/auth.css";
import "./styles/public.css";
import "./styles/polish.css";
import "./styles/filters.css";
import "./styles/dashboard.css";
import "./styles/landing.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

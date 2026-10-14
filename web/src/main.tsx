import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./fonts";
import { App } from "./App";

const el = document.getElementById("root");
if (!el) throw new Error("Thiếu #root");
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

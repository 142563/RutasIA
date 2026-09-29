/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Django sirve el build en /static/app/ y resuelve la API.
// En desarrollo (npm run dev) Vite reenvía la API a Django en el puerto 8000.
const django = "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/app/" : "/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: django },
      "/admin": { target: django },
      "/accounts": { target: django },
      "/clasico": { target: django },
      "/static": { target: django },
    },
  },
  // dist/app/ → Django lo publica como /static/app/ (sin prefijos, que fallan en Windows)
  build: { outDir: "dist/app", emptyOutDir: true },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
}));

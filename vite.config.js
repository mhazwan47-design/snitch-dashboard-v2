import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/snitch-dashboard-v2/",
  build: {
    outDir: "docs",
    emptyOutDir: false
  }
});

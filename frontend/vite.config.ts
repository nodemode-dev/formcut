import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as {
  version: string;
};

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    host: false,
    port: 3040,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8040",
    },
  },
  preview: {
    host: false,
    port: 3041,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8040",
    },
  },
});

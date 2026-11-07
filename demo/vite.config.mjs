import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(resolve(here, "../frontend/package.json"), "utf-8"));

const classicScript = {
  name: "formcut-demo-classic-script",
  transformIndexHtml: {
    order: "post",
    handler(html) {
      const scripts = [];
      const rest = html
        .replace(/<script type="module" crossorigin src="([^"]+)"><\/script>/g, (_match, src) => {
          scripts.push(src);
          return "";
        })
        .replace(/ crossorigin/g, "");
      return rest.replace("</body>", `${scripts.map((src) => `<script defer src="${src}"></script>`).join("")}</body>`);
    },
  },
};

export default {
  root: resolve(here, "src"),
  base: "./",
  publicDir: resolve(here, "src/public"),
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  plugins: [classicScript],
  server: { host: false, port: 3042, strictPort: true },
  preview: { host: false, port: 3043, strictPort: true },
  build: {
    outDir: resolve(here),
    emptyOutDir: false,
    cssCodeSplit: false,
    modulePreload: false,
    assetsInlineLimit: 0,
    target: "es2022",
    rollupOptions: {
      output: {
        format: "iife",
        entryFileNames: "assets/demo.js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
};

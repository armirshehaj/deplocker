import fs from "fs";
import path from "path";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default ({ mode }: { mode: string }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    define: {
      // The web app reaches the API under /api on its own address
      API_URL: JSON.stringify("/api"),
    },
    server: {
      // Hands /api to the API without the prefix, as Caddy does in containers
      proxy: {
        "/api": {
          target: "http://localhost:8080",
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
      // WebAuthn needs a real https origin on a real domain
      ...(env.DEV_HTTPS
        ? {
            host: "lvh.me",
            allowedHosts: ["lvh.me"],
            https: {
              key: fs.readFileSync(path.resolve(__dirname, "lvh.me-key.pem")),
              cert: fs.readFileSync(path.resolve(__dirname, "lvh.me.pem")),
            },
          }
        : {}),
    },
  });
};

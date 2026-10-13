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
      API_URL: JSON.stringify(env.API_URL),
    },
    // WebAuthn needs a real https origin on a real domain. The API is proxied
    // rather than called directly so page and API share one origin: the session
    // and challenge cookies are SameSite=strict and lvh.me -> localhost is cross-site.
    server: env.DEV_HTTPS
      ? {
          host: "lvh.me",
          allowedHosts: ["lvh.me"],
          https: {
            key: fs.readFileSync(path.resolve(__dirname, "lvh.me-key.pem")),
            cert: fs.readFileSync(path.resolve(__dirname, "lvh.me.pem")),
          },
          proxy: {
            "/api": {
              target: "http://localhost:8080",
              rewrite: (p) => p.replace(/^\/api/, ""),
            },
          },
        }
      : undefined,
  });
};

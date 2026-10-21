import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode, command }) => {
  if (mode === "offline" && command !== "serve")
    throw new Error(
      "O modo offline está disponível somente no servidor de desenvolvimento.",
    );
  const offline = command === "serve" && mode === "offline";
  const env: Record<string, string> = offline
    ? {}
    : loadEnv(mode, process.cwd(), "");
  const developmentAuth =
    mode === "development" &&
    env.APP_ENV === "development" &&
    env.AUTH_MODE === "development" &&
    (env.DEV_AUTH_TOKEN ?? "").length >= 32;
  return {
    envDir: offline ? false : undefined,
    define: { __LOCAL_DEMO__: JSON.stringify(offline) },
    plugins: [
      react(),
      {
        name: "local-api-origin-guard",
        configureServer(server) {
          server.middlewares.use((req, res, next) => {
            if (req.url?.startsWith("/api") && req.headers.origin) {
              const expected = new Set([
                `http://127.0.0.1:${server.config.server.port}`,
                `http://localhost:${server.config.server.port}`,
              ]);
              if (!expected.has(req.headers.origin)) {
                res.statusCode = 403;
                res.end();
                return;
              }
            }
            next();
          });
        },
      },
    ],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      allowedHosts: ["localhost", "127.0.0.1"],
      proxy: offline
        ? undefined
        : {
            "/api": {
              target: "http://127.0.0.1:8000",
              configure(proxy) {
                if (developmentAuth)
                  proxy.on("proxyReq", (proxyRequest) => {
                    proxyRequest.setHeader(
                      "Authorization",
                      `Bearer ${env.DEV_AUTH_TOKEN}`,
                    );
                  });
              },
            },
          },
    },
  };
});

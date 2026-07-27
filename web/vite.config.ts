import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const BACKEND = process.env.KOPI_DASHBOARD_URL ?? "http://127.0.0.1:9119";

/**
 * In production the Python `kopi dashboard` server injects a one-shot
 * session token into `index.html` (see `kopi_cli/web_server.py`). The
 * Vite dev server serves its own `index.html`, so unless we forward that
 * token, every protected `/api/*` call 401s.
 *
 * This plugin fetches the running dashboard's `index.html` on each dev page
 * load, scrapes the `window.__KOPI_SESSION_TOKEN__` assignment, and
 * re-injects it into the dev HTML. No-op in production builds.
 */
function kopiDevToken(): Plugin {
  const TOKEN_RE = /window\.__KOPI_SESSION_TOKEN__\s*=\s*"([^"]+)"/;
  const EMBEDDED_RE =
    /window\.__KOPI_DASHBOARD_EMBEDDED_CHAT__\s*=\s*(true|false)/;

  return {
    name: "kopi:dev-session-token",
    apply: "serve",
    async transformIndexHtml() {
      try {
        const res = await fetch(BACKEND, { headers: { accept: "text/html" } });
        const html = await res.text();
        const match = html.match(TOKEN_RE);
        if (!match) {
          console.warn(
            `[kopi] Could not find session token in ${BACKEND} — ` +
              `is \`kopi dashboard\` running? /api calls will 401.`,
          );
          return;
        }
        const embeddedMatch = html.match(EMBEDDED_RE);
        const embeddedJs = embeddedMatch ? embeddedMatch[1] : "true";
        return [
          {
            tag: "script",
            injectTo: "head",
            children:
              `window.__KOPI_SESSION_TOKEN__="${match[1]}";` +
              `window.__KOPI_DASHBOARD_EMBEDDED_CHAT__=${embeddedJs};`,
          },
        ];
      } catch (err) {
        console.warn(
          `[kopi] Dashboard at ${BACKEND} unreachable — ` +
            `start it with \`kopi dashboard\` or set KOPI_DASHBOARD_URL. ` +
            `(${(err as Error).message})`,
        );
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), kopiDevToken()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@kopi/shared": path.resolve(__dirname, "../apps/shared/src"),
    },
    // When @nous-research/ui is symlinked via `file:../../design-language`,
    // Node's module resolution would pick up shared deps from
    // design-language/node_modules/*, giving us two copies + breaking
    // hooks (useRef-of-null), webgl contexts, etc. Force everything that
    // exists in BOTH places to use the dashboard's copy.
    //
    // Don't list packages here that only exist in the DS (nanostores,
    // @nanostores/react) — Vite dedupe errors out when it can't find
    // them at the project root.
    dedupe: [
      "react",
      "react-dom",
      "@react-three/fiber",
      "@observablehq/plot",
      "three",
      "leva",
      "gsap",
    ],
  },
  // 资源 URL 的 base 必须在**运行时**决定,不能烘进构建产物。
  //
  // dashboard 会被网站以路径前缀代理暴露(`/i/<customerId>/*` → 实例根 `/*`)。
  // 服务端已经把 index.html 里的绝对资源路径重写成带前缀的形式
  // (`kopi_cli/web_server.py` 的 `_serve_index`,读 `X-Forwarded-Prefix`),
  // 但**字符串替换够不着 JS 内部运行时拼出来的 URL** —— Vite 的 preload 助手
  // 与动态 import 用的是构建时烘死的 `base`(默认 `/`)。
  //
  // 症状:落地页能起来(index.html 被重写过,入口 chunk 正常执行),但任何
  // 懒加载路由都白屏,控制台是一串 `GET /assets/<chunk>.js 404` —— 注意路径
  // 里没有 `/i/<id>/` 前缀。v12 换 rolldown + 懒加载路由后每个页面都要单独拉
  // chunk,这条路径才第一次被走到;之前是单文件 bundle,没有运行时加载,所以
  // 同样的 base 问题一直没暴露。
  //
  // 这里让 JS 侧改用运行时全局 `window.__KOPI_BASE_PATH__`(引擎在入口模块
  // **之前**的 bootstrap `<script>` 里注入,根路径部署时为空串,行为与原先
  // 完全一致)。index.html / CSS 维持绝对路径,继续走服务端重写那条已验证的路。
  //
  // 不用 `base: "./"` 的原因:相对路径按**当前 URL 深度**解析,`/i/<id>/chat`
  // 恰好能对,但嵌套一层的路由就会解析到 `/i/<id>/xxx/assets/...`;而且改成
  // 相对后服务端那条 `href="/assets/` 的重写规则也匹配不上了。
  experimental: {
    renderBuiltUrl(filename, { hostType }) {
      if (hostType === "js") {
        return {
          runtime: `((globalThis.__KOPI_BASE_PATH__ ?? "") + "/" + ${JSON.stringify(
            filename
          )})`,
        };
      }
      return { relative: false };
    },
  },
  build: {
    outDir: "../kopi_cli/web_dist",
    emptyOutDir: true,
    // Shell stays a bit over Vite's 500 kB default after vendor splits;
    // page/xterm chunks load on demand. Keep a modest ceiling so a true
    // regression still warns.
    chunkSizeWarningLimit: 600,
    // Split heavy vendors so the first dashboard paint does not download
    // xterm/three/plot/etc. until a route actually needs them. Lazy page
    // imports in App.tsx create the route boundaries; these groups keep
    // shared node_modules out of every page chunk.
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20_000,
          groups: [
            {
              name: "react-vendor",
              test: /node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)([\\/]|$)/,
            },
            {
              name: "xterm",
              test: /node_modules[\\/]@xterm[\\/]/,
            },
            {
              name: "three",
              test: /node_modules[\\/](three|@react-three)([\\/]|$)/,
            },
            {
              name: "plot",
              test: /node_modules[\\/]@observablehq[\\/]plot([\\/]|$)/,
            },
            {
              name: "motion",
              test: /node_modules[\\/](motion|framer-motion)([\\/]|$)/,
            },
            {
              name: "ui",
              test: /node_modules[\\/]@nous-research[\\/]ui([\\/]|$)/,
            },
            {
              name: "vendor",
              test: /node_modules[\\/]/,
            },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: BACKEND,
        ws: true,
      },
      // Same host as `kopi dashboard` must serve these; Vite has no
      // dashboard-plugins/* files, so without this, plugin scripts 404
      // or receive index.html in dev.
      "/dashboard-plugins": BACKEND,
    },
  },
});

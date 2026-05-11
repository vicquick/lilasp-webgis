import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'WEB_');
  return {
    server: {
      port: 5173,
      proxy: {
        '/qgisserver': { target: 'http://localhost:8080', changeOrigin: true, rewrite: (p) => p.replace(/^\/qgisserver/, '/qgisserver') },
        '/tiles':      { target: 'http://localhost:3000', changeOrigin: true, rewrite: (p) => p.replace(/^\/tiles/, '') },
        '/whoami':     { target: 'http://localhost:5000', changeOrigin: true },
        '/services.json': { target: 'http://localhost:8080', changeOrigin: true },
      },
    },
    build: { target: 'es2022', sourcemap: true, outDir: 'dist' },
    define: {
      __WEB_QGIS_BASE__:          JSON.stringify(env.WEB_QGIS_BASE          ?? '/qgisserver'),
      __WEB_TILES_BASE__:         JSON.stringify(env.WEB_TILES_BASE         ?? '/tiles'),
      __WEB_WHOAMI__:             JSON.stringify(env.WEB_WHOAMI             ?? '/whoami'),
      __WEB_SERVICES_JSON_URL__:  JSON.stringify(env.WEB_SERVICES_JSON_URL  ?? '/services.json'),
    },
  };
});

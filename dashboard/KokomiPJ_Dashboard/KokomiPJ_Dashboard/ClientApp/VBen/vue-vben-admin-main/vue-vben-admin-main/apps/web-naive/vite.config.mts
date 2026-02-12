import { defineConfig } from '@vben/vite-config';

export default defineConfig(async () => {
  return {
    application: {},
    vite: {
      base: '/app/',
      build: {
        // ✅ 让 manifest 放到 outDir 根，避免 .vite 点目录被漏拷
        manifest: 'manifest.json',
        // ✅ 明确 outDir（先用默认 dist 验证）
        outDir: 'dist',
        // ✅ 明确 assetsDir（不让任何封装改掉）
        assetsDir: 'assets',
        emptyOutDir: true,
      },
      server: {
        proxy: {
          '/api': {
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api/, ''),
            target: 'http://localhost:5320/api',
            ws: true,
          },
        },
      },
    },
  };
});

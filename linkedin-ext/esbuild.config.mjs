import { build, context } from 'esbuild';
import { cp, mkdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';

const watch = process.argv.includes('--watch');

const entries = [
  'src/background/service-worker.ts',
  'src/content/linkedin-profile.ts',
  'src/content/linkedin-feed.ts',
  'src/content/linkedin-messaging.ts',
  'src/content/linkedin-post-helper.ts',
  'src/content/application-autofill.ts',
  'src/content/application-reporter.ts',
  'src/popup/popup.ts',
  'src/options/options.ts'
];

const sharedOpts = {
  entryPoints: entries,
  bundle: true,
  outdir: 'dist',
  format: 'esm',
  target: 'chrome120',
  outbase: 'src',
  sourcemap: watch ? 'inline' : false,
  minify: !watch,
  logLevel: 'info'
};

async function copyStatic() {
  if (existsSync('dist')) {
    // Asegurar subcarpetas para los recursos estáticos
  }
  await mkdir('dist/popup', { recursive: true });
  await mkdir('dist/options', { recursive: true });
  await mkdir('dist/content', { recursive: true });
  await mkdir('dist/icons', { recursive: true });

  await cp('manifest.json', 'dist/manifest.json');
  await cp('src/popup/popup.html', 'dist/popup/popup.html');
  await cp('src/popup/popup.css', 'dist/popup/popup.css');
  await cp('src/options/options.html', 'dist/options/options.html');
  await cp('src/content/overlay.css', 'dist/content/overlay.css');
  if (existsSync('public/icons')) {
    await cp('public/icons', 'dist/icons', { recursive: true });
  }
}

if (watch) {
  const ctx = await context(sharedOpts);
  await ctx.watch();
  await copyStatic();
  console.log('[esbuild] watching for changes...');
} else {
  // Limpia dist antes del build de producción
  if (existsSync('dist')) {
    await rm('dist', { recursive: true, force: true });
  }
  await build(sharedOpts);
  await copyStatic();
  console.log('[esbuild] build complete -> dist/');
}

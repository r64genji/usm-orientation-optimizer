import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const siteDir = path.resolve(__dirname, '..');
const distDir = path.resolve(siteDir, 'dist');

console.log('[BUILD] Building proposal site into dist/...');

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// Copy index.html, styles.css, app.js, package.json
const filesToCopy = ['index.html', 'styles.css', 'app.js', 'package.json'];

for (const file of filesToCopy) {
  const src = path.join(siteDir, file);
  const dest = path.join(distDir, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest);
    console.log(`[BUILD] Copied ${file} -> dist/${file}`);
  } else {
    console.warn(`[BUILD] Source file not found: ${file}`);
  }
}

console.log('[BUILD] Build completed successfully.');

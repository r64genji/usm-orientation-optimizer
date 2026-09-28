import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const siteDir = path.resolve(__dirname, '..');

const htmlPath = path.join(siteDir, 'index.html');
const cssPath = path.join(siteDir, 'styles.css');
const jsPath = path.join(siteDir, 'app.js');

assert(fs.existsSync(htmlPath), 'index.html must exist');
assert(fs.existsSync(cssPath), 'styles.css must exist');
assert(fs.existsSync(jsPath), 'app.js must exist');

const html = fs.readFileSync(htmlPath, 'utf8');
const css = fs.readFileSync(cssPath, 'utf8');
const js = fs.readFileSync(jsPath, 'utf8');

// 1) 12 section class page
const pageMatches = html.match(/<section[^>]*class=["'][^"']*\bpage\b[^"']*["']/g) || [];
assert.strictEqual(pageMatches.length, 12, `Expected 12 section class page elements, found ${pageMatches.length}`);

// 2) >=8 svg
const svgMatches = html.match(/<svg\b/g) || [];
assert(svgMatches.length >= 8, `Expected >= 8 svg elements, found ${svgMatches.length}`);

// 3) @page and A4
assert(css.includes('@page'), 'styles.css must contain @page');
assert(css.includes('A4'), 'styles.css must contain A4');

// 4) localStorage
assert(js.includes('localStorage'), 'app.js must contain localStorage');

// 5) reset and print hooks
assert(
  (js.includes('reset') || html.includes('reset')) && (js.includes('print') || html.includes('print')),
  'reset and print hooks must exist'
);

// 6) viewport meta
assert(
  /<meta[^>]*name=["']viewport["'][^>]*>/i.test(html),
  'index.html must contain viewport meta tag'
);
// 5) toolbar buttons and hooks (save, reset, export, print, edit-toggle)
assert(html.includes('id="btn-save"'), 'index.html must contain btn-save');
assert(html.includes('id="btn-reset"'), 'index.html must contain btn-reset');
assert(html.includes('id="btn-export-data"'), 'index.html must contain btn-export-data');
assert(html.includes('id="btn-print"'), 'index.html must contain btn-print');
assert(html.includes('id="btn-edit-toggle"'), 'index.html must contain btn-edit-toggle');
assert(html.includes('id="status-pill"'), 'index.html must contain status-pill');
assert(
  (js.includes('reset') || html.includes('reset')) && (js.includes('print') || html.includes('print')),
  'reset and print hooks must exist'
);
assert(js.includes('btn-edit-toggle') || js.includes('editToggle'), 'app.js must support edit toggle');
assert(/zero door checks/i.test(html), 'index.html must contain zero door checks');

// 8) rejects http:// or https://
assert(!html.includes('http://'), 'index.html must not contain http://');
assert(!html.includes('https://'), 'index.html must not contain https://');
assert(!css.includes('http://'), 'styles.css must not contain http://');
assert(html.includes('09:00'), 'index.html must contain 09:00');
assert(html.includes('154'), 'index.html must contain 154');
assert(/5\s+coach/i.test(html), 'index.html must contain 5 coach');
assert(/3\s+electric/i.test(html), 'index.html must contain 3 electric');
assert(/zero door checks/i.test(html), 'index.html must contain zero door checks');
assert(html.includes('180 s') || html.includes('180s'), 'index.html must include conservative 180s dwell');
assert(!html.includes('Capacity 44'), 'index.html must not contain obsolete Capacity 44');
assert(!html.includes('75 seconds'), 'index.html must not contain obsolete 75 seconds disembark');
console.log('All verification assertions passed.');

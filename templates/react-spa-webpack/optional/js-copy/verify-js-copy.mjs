#!/usr/bin/env node
/**
 * Proves `js-copy/` (built by scripts/emit-js-copy.mjs) is actually free of
 * the TypeScript toolchain it was generated to hide. Run after every build:
 *   npm run js-copy:build && npm run js-copy:verify
 *
 * A constraint enforced on the primary artifact (the transpiled source) is
 * NOT automatically enforced on documents generated beside it — a README or
 * footer that credits its sources BY PATH ("gerado a partir de
 * src/foo.ts") discloses the excluded toolchain even when zero .ts files
 * exist in the tree. Name generated sources by ROLE instead ("gerado a
 * partir do código-fonte da aplicação"); this check fails loudly if a
 * generated document does it by path instead.
 */
import fs from 'fs';
import path from 'path';

const OUT_DIR = path.resolve(process.cwd(), 'js-copy');
const BANNED_FILENAME_RE = /\.tsx?$|^tsconfig.*\.json$/;
const BANNED_TEXT_RE = /typescript|\.tsx?\b/i;
const TEXT_DOCUMENT_EXTENSIONS = new Set(['.md', '.txt', '.html']);

function collectFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(fullPath, out);
    } else {
      out.push(fullPath);
    }
  }
  return out;
}

function findFailures(files) {
  const failures = [];
  for (const filePath of files) {
    const relPath = path.relative(OUT_DIR, filePath);
    if (BANNED_FILENAME_RE.test(path.basename(filePath))) {
      failures.push(`${relPath}: TypeScript source/config file in a JS-only delivery`);
      continue;
    }
    if (TEXT_DOCUMENT_EXTENSIONS.has(path.extname(filePath).toLowerCase())) {
      const text = fs.readFileSync(filePath, 'utf8');
      if (BANNED_TEXT_RE.test(text)) {
        failures.push(`${relPath}: mentions TypeScript / a .ts(x) path — name sources by role instead`);
      }
    }
  }
  return failures;
}

function main() {
  if (!fs.existsSync(OUT_DIR)) {
    console.error(`js-copy verify: ${OUT_DIR} does not exist — run "npm run js-copy:build" first.`);
    process.exit(1);
  }

  const files = collectFiles(OUT_DIR);
  const failures = findFailures(files);

  if (failures.length > 0) {
    console.error('js-copy verify FAILED:');
    for (const failure of failures) console.error(`  - ${failure}`);
    process.exit(1);
  }

  console.log(`js-copy verify OK — ${files.length} files, zero TypeScript surface.`);
}

main();

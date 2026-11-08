import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { fileFindings } from './assertion-weakening.cjs';

const spec = (matcher: string): string =>
  `it('computes', () => {\n  expect(compute()).${matcher}(5);\n});\n`;

const GATE = path.join(__dirname, 'assertion-weakening.cjs');
const GATE_ENV = { ...process.env, CI: '', GITHUB_ACTIONS: '', GITHUB_EVENT_PATH: '', TEST_CHANGE_OK: '' };

describe('assertion weakening gate', () => {
  it.each([
    ['toBe', 'toBeGreaterThan'],
    ['toBe', 'toBeLessThan'],
    ['toEqual', 'toBeGreaterThanOrEqual'],
    ['toStrictEqual', 'toBeLessThanOrEqual'],
  ])('flags %s loosened to %s', (before, after) => {
    expect(fileFindings('a.test.ts', spec(before), spec(after))).toHaveLength(1);
  });

  it('names the matchers in the finding', () => {
    expect(fileFindings('a.test.ts', spec('toBe'), spec('toBeGreaterThan'))[0]).toContain(
      'toBe loosened to toBeGreaterThan',
    );
  });

  it.each(['toBeGreaterThan', 'toBeLessThan'])('ignores an assertion that was always %s', (matcher) => {
    expect(fileFindings('a.test.ts', spec(matcher), spec(matcher))).toEqual([]);
  });

  it.each(['toBeGreaterThan', 'toBeLessThan'])('ignores %s strengthened to toBe', (matcher) => {
    expect(fileFindings('a.test.ts', spec(matcher), spec('toBe'))).toEqual([]);
  });

  it('ignores an unchanged equality', () => {
    expect(fileFindings('a.test.ts', spec('toBe'), spec('toBe'))).toEqual([]);
  });

  it('splits it.each tests so their matchers are not folded into the previous test', () => {
    const each = (matcher: string): string =>
      `it('first', () => {\n  expect(a).toBe(1);\n});\nit.each([[1], [2]])('second %s', (n) => {\n  expect(n).${matcher}(1);\n});\n`;
    expect(fileFindings('a.test.ts', each('toBe'), each('toBeGreaterThan'))).toHaveLength(1);
  });

  it('ignores a negated matcher swap', () => {
    const negated = "it('computes', () => {\n  expect(x).not.toBe(5);\n});\n";
    expect(fileFindings('a.test.ts', negated, spec('toBeGreaterThan'))).toEqual([]);
  });
});

describe('assertion weakening gate as a command', () => {
  it('blocks a staged weakening when HEAD is the merge-base', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
      });
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBe'));
      run('add', '.');
      run('commit', '-qm', 'init');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBeGreaterThan'));
      run('add', '.');
      const result = spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' });
      expect(result.status).toBe(1);
      expect(result.stdout).toContain('toBe loosened to toBeGreaterThan');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('does not block the first commit of a repo with no HEAD', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    try {
      execFileSync('git', ['init', '-q'], { cwd: dir, stdio: 'ignore' });
      expect(spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' }).status).toBe(0);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

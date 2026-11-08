import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { fileFindings } from './assertion-weakening.cjs';

const spec = (matcher: string): string =>
  `it('computes', () => {\n  expect(compute()).${matcher}(5);\n});\n`;

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

  it('blocks a staged weakening when HEAD is the merge-base', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer => execFileSync('git', args, { cwd: dir, stdio: 'ignore' });
    run('init', '-q', '-b', 'main');
    run('config', 'user.email', 'a@b');
    run('config', 'user.name', 't');
    fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBe'));
    run('add', '.');
    run('commit', '-qm', 'init');
    fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBeGreaterThan'));
    run('add', '.');
    const env = { ...process.env, CI: '', GITHUB_ACTIONS: '', TEST_CHANGE_OK: '' };
    const gate = path.join(__dirname, 'assertion-weakening.cjs');
    const result = spawnSync('node', [gate], { cwd: dir, env, encoding: 'utf8' });
    fs.rmSync(dir, { recursive: true, force: true });
    expect(result.status).toBe(1);
  });

  it('ignores a negated matcher swap', () => {
    const negated = "it('computes', () => {\n  expect(x).not.toBe(5);\n});\n";
    expect(fileFindings('a.test.ts', negated, spec('toBeGreaterThan'))).toEqual([]);
  });
});

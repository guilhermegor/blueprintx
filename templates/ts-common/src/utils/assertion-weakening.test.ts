import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { collect, fileFindings, justification } from './assertion-weakening.cjs';

const spec = (matcher: string): string =>
  `it('computes', () => {\n  expect(compute()).${matcher}(5);\n});\n`;

const UNCHANGED_LINES = 20;
const UNCHANGED = 'const unchanged = 1;\n'.repeat(UNCHANGED_LINES);

const GATE = path.join(__dirname, 'assertion-weakening.cjs');
const CLEAN_ENV = Object.fromEntries(
  Object.entries(process.env).filter(([name]) => !name.startsWith('GIT_')),
);
const GATE_ENV = {
  ...CLEAN_ENV,
  CI: '',
  GITHUB_ACTIONS: '',
  GITHUB_BASE_REF: '',
  GITHUB_EVENT_PATH: '',
  TEST_CHANGE_OK: '',
};

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

});

describe('assertion weakening gate matching', () => {
  it('fails closed when the staged diff cannot be read', () => {
    expect(() => collect('0000000000000000000000000000000000000000')).toThrow();
  });

});

describe('assertion weakening gate justification', () => {
  const withEvent = (event: string, check: () => void): void => {
    const saved = process.env.GITHUB_EVENT_PATH;
    process.env.GITHUB_EVENT_PATH = event;
    try {
      check();
    } finally {
      process.env.GITHUB_EVENT_PATH = saved ?? '';
    }
  };

  it('rejects an unfilled <reason> placeholder', () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'aw-')), 'event.json');
    fs.writeFileSync(file, JSON.stringify({ pull_request: { body: 'test-change-ok: <reason>' } }));
    withEvent(file, () => expect(justification('HEAD')).toBe(''));
  });

  it('takes a real reason that follows a placeholder line in the same text', () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'aw-')), 'event.json');
    const body = 'test-change-ok: <reason>\ntest-change-ok: the old value was wrong';
    fs.writeFileSync(file, JSON.stringify({ pull_request: { body } }));
    withEvent(file, () => expect(justification('HEAD')).toBe('the old value was wrong'));
  });

  it('survives an unreadable event file', () => {
    withEvent('/nonexistent/event.json', () => expect(justification('HEAD')).toBe(''));
  });

  it('rejects an unfilled <reason> placeholder in TEST_CHANGE_OK', () => {
    const names = ['CI', 'GITHUB_ACTIONS', 'TEST_CHANGE_OK'];
    const saved = names.map((name) => process.env[name] || '');
    names.forEach((name) => {
      process.env[name] = '';
    });
    process.env.TEST_CHANGE_OK = '<reason>';
    try {
      withEvent('', () => expect(justification('HEAD')).toBe(''));
    } finally {
      names.forEach((name, index) => {
        process.env[name] = saved[index];
      });
    }
  });

});

describe('assertion weakening gate justification in a branch', () => {
  it('does not take a justification reason from the next line', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
        env: CLEAN_ENV,
      });
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBe'));
      run('add', '.');
      run('commit', '-qm', 'init');
      run('checkout', '-q', '-b', 'feat');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBeGreaterThan'));
      run('add', '.');
      run('commit', '-qm', 'weaken', '-m', 'test-change-ok:', '-m', 'unrelated line');
      fs.writeFileSync(path.join(dir, 'b.txt'), 'x');
      run('add', '.');
      const result = spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' });
      expect(result.status).toBe(1);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('splits it.each tests so their matchers are not folded into the previous test', () => {
    const each = (matcher: string): string =>
      `it('first', () => {\n  expect(a).toBe(1);\n});\nit.each([[1], [2]])('second %s', (n) => {\n  expect(n).${matcher}(1);\n});\n`;
    expect(fileFindings('a.test.ts', each('toBe'), each('toBeGreaterThan'))).toHaveLength(1);
  });

  it('flags a weakening next to a non-matcher .toFixed() call', () => {
    const before = "it('f', () => {\n  expect(x.toFixed(2)).toBe('1.00');\n});\n";
    const after = "it('f', () => {\n  expect(x).toBeGreaterThan(1);\n});\n";
    expect(fileFindings('a.test.ts', before, after)).toHaveLength(1);
  });

  it('does not flag an added inequality assertion above an existing equality', () => {
    const before = "it('f', () => {\n  expect(x).toBe(5);\n});\n";
    const after = "it('f', () => {\n  expect(x).toBeGreaterThan(0);\n  expect(x).toBe(5);\n});\n";
    expect(fileFindings('a.test.ts', before, after)).toEqual([]);
  });

  it('splits fit/xit and ignores re.test() calls', () => {
    const src = (m: string): string =>
      `fit('a', () => {\n  expect(a).${m}(1);\n});\nit('b', () => {\n  re.test('x');\n  expect(b).toBe(1);\n});\n`;
    expect(fileFindings('a.test.ts', src('toBe'), src('toBeGreaterThan'))).toHaveLength(1);
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
        env: CLEAN_ENV,
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

  it('checks a renamed test file under its new path', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
        env: CLEAN_ENV,
      });
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), UNCHANGED + spec('toBe'));
      run('add', '.');
      run('commit', '-qm', 'init');
      run('mv', 'a.test.ts', 'b.test.ts');
      fs.writeFileSync(path.join(dir, 'b.test.ts'), UNCHANGED + spec('toBeGreaterThan'));
      run('add', '.');
      const result = spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' });
      expect(result.status).toBe(1);
      expect(result.stdout).toContain('b.test.ts: computes: toBe loosened to toBeGreaterThan');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('assertion weakening gate as a command, edge cases', () => {
  it('checks a test file whose name git would C-quote', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
        env: CLEAN_ENV,
      });
    const file = path.join(dir, 'café.test.ts');
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      fs.writeFileSync(file, spec('toBe'));
      run('add', '.');
      run('commit', '-qm', 'init');
      fs.writeFileSync(file, spec('toBeLessThan'));
      run('add', '.');
      const result = spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' });
      expect(result.status).toBe(1);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('does not block the first commit of a repo with no HEAD', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    try {
      execFileSync('git', ['init', '-q'], { cwd: dir, stdio: 'ignore', env: CLEAN_ENV });
      expect(spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' }).status).toBe(0);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('assertion weakening gate in the middle of a merge', () => {
  const gateAfterMerge = (mainMatcher: string, featMatcher: string): number | null => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
        env: CLEAN_ENV,
      });
    const commitFile = (name: string, content: string): void => {
      fs.writeFileSync(path.join(dir, name), content);
      run('add', '.');
      run('commit', '-qm', `edit ${name}`, '--allow-empty');
    };
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      commitFile('a.test.ts', spec('toBe'));
      run('checkout', '-q', '-b', 'feat');
      commitFile('own.txt', 'own');
      commitFile('a.test.ts', spec(featMatcher));
      run('checkout', '-q', 'main');
      commitFile('theirs.txt', 'theirs');
      commitFile('a.test.ts', spec(mainMatcher));
      run('checkout', '-q', 'feat');
      run('merge', '-q', '--no-commit', '--no-ff', 'main');
      return spawnSync('node', [GATE], { cwd: dir, env: GATE_ENV, encoding: 'utf8' }).status;
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  };

  it('does not charge a weakening merged in from main to the branch', () => {
    expect(gateAfterMerge('toBeGreaterThan', 'toBe')).toBe(0);
  });

  it('still blocks a weakening the branch itself authored', () => {
    expect(gateAfterMerge('toBe', 'toBeGreaterThan')).toBe(1);
  });
});

describe('assertion weakening gate fails closed', () => {
  it('refuses to pass when git is unusable', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const env = { ...GATE_ENV, GIT_CEILING_DIRECTORIES: path.dirname(dir) };
    try {
      expect(spawnSync('node', [GATE], { cwd: dir, env, encoding: 'utf8' }).status).toBe(1);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('falls back to the commit trailer when the PR body holds a placeholder', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    const event = `${dir}-event.json`;
    fs.writeFileSync(event, JSON.stringify({ pull_request: { body: 'test-change-ok: <reason>' } }));
    const run = (...args: string[]): Buffer =>
      execFileSync('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: dir,
        stdio: 'ignore',
        env: CLEAN_ENV,
      });
    try {
      run('init', '-q');
      run('checkout', '-q', '-b', 'main');
      run('config', 'user.email', 'a@b');
      run('config', 'user.name', 't');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBe'));
      run('add', '.');
      run('commit', '-qm', 'init');
      run('checkout', '-q', '-b', 'feat');
      fs.writeFileSync(path.join(dir, 'a.test.ts'), spec('toBeGreaterThan'));
      run('add', '.');
      run('commit', '-qm', 'weaken', '-m', 'test-change-ok: the old value was wrong');
      fs.writeFileSync(path.join(dir, 'b.txt'), 'x');
      run('add', '.');
      const env = { ...GATE_ENV, GITHUB_EVENT_PATH: event };
      expect(spawnSync('node', [GATE], { cwd: dir, env, encoding: 'utf8' }).status).toBe(0);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
      fs.rmSync(event, { force: true });
    }
  });
});

describe('assertion weakening hook wiring', () => {
  it('fails the pre-commit hook when the gate file is missing', () => {
    const hook = fs.readFileSync(path.join(process.cwd(), '.husky', 'pre-commit'), 'utf8');
    const lines = hook.split('\n');
    const script = lines.slice(lines.findIndex((line) => line.startsWith('gate='))).join('\n');
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aw-'));
    try {
      fs.writeFileSync(path.join(dir, 'package.json'), '{"main":"x.js"}');
      fs.writeFileSync(path.join(dir, 'x.js'), '');
      expect(spawnSync('sh', ['-c', script], { cwd: dir, encoding: 'utf8' }).status).toBe(1);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

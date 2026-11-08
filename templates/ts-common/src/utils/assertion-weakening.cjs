const { execFileSync } = require('node:child_process');
const fs = require('node:fs');

const RE_TEST_PATH = /\.(test|spec)\.(ts|tsx|js|jsx)$/;
const RE_TEST_START = /\b(?:it|test)(?:\.each\((?:[^()]|\([^()]*\))*\)|\.\w+)?\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;
const RE_MATCHER = /\.(not\.)?(to[A-Z]\w*)\(/g;
const RE_JUSTIFICATION = /^\s*test-change-ok:\s*(\S.*)$/im;

const EQUALITY_MATCHERS = new Set(['toBe', 'toEqual', 'toStrictEqual']);
const INEQUALITY_MATCHERS = new Set([
  'toBeGreaterThan',
  'toBeLessThan',
  'toBeGreaterThanOrEqual',
  'toBeLessThanOrEqual',
]);

function splitTests(source) {
  const starts = [...source.matchAll(RE_TEST_START)];
  const seen = new Map();
  return starts.map((match, index) => {
    const end = index + 1 < starts.length ? starts[index + 1].index : source.length;
    const count = seen.get(match[2]) ?? 0;
    seen.set(match[2], count + 1);
    return { key: `${match[2]}#${count}`, name: match[2], body: source.slice(match.index, end) };
  });
}

function matchers(body) {
  return [...body.matchAll(RE_MATCHER)].map((match) => ({
    negated: Boolean(match[1]),
    name: match[2],
  }));
}

function isLoosened(before, after) {
  return (
    !before.negated &&
    !after.negated &&
    EQUALITY_MATCHERS.has(before.name) &&
    INEQUALITY_MATCHERS.has(after.name)
  );
}

function testFindings(path, oldTest, newTest) {
  const oldMatchers = matchers(oldTest.body);
  const newMatchers = matchers(newTest.body);
  return oldMatchers
    .slice(0, newMatchers.length)
    .map((before, index) => [before, newMatchers[index]])
    .filter(([before, after]) => isLoosened(before, after))
    .map(([before, after]) => `${path}: ${newTest.name}: ${before.name} loosened to ${after.name}`);
}

function fileFindings(path, oldSource, newSource) {
  const oldTests = new Map(splitTests(oldSource).map((test) => [test.key, test]));
  return splitTests(newSource)
    .filter((test) => oldTests.has(test.key))
    .flatMap((test) => testFindings(path, oldTests.get(test.key), test));
}

function git(args) {
  try {
    return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  } catch {
    return '';
  }
}

function defaultBranch() {
  const candidates = ['origin/main', 'origin/master', 'main', 'master'];
  return candidates.find((ref) => git(['rev-parse', '--verify', '--quiet', ref]).trim()) ?? '';
}

function justification(base) {
  const isCi = Boolean(process.env.CI || process.env.GITHUB_ACTIONS);
  const fromEnv = isCi ? '' : (process.env.TEST_CHANGE_OK ?? '').trim();
  if (fromEnv) return fromEnv;
  const eventPath = process.env.GITHUB_EVENT_PATH;
  const prBody = eventPath ? (JSON.parse(fs.readFileSync(eventPath, 'utf8')).pull_request?.body ?? '') : '';
  const trailers = git(['log', `${base}..HEAD`, '--format=%B']);
  const match = RE_JUSTIFICATION.exec(prBody) ?? RE_JUSTIFICATION.exec(trailers);
  return match ? match[1].trim() : '';
}

function collect(base) {
  const rows = git(['diff', '--cached', '--name-status', '--find-renames', base])
    .split('\n')
    .map((line) => line.split('\t'))
    .filter((parts) => parts.length >= 2 && RE_TEST_PATH.test(parts[parts.length - 1]));
  return rows.flatMap((parts) => {
    const oldSource = git(['show', `${base}:${parts[1]}`]);
    const newSource = git(['show', `:${parts[parts.length - 1]}`]);
    return oldSource && newSource ? fileFindings(parts[parts.length - 1], oldSource, newSource) : [];
  });
}

function hasCommits() {
  return Boolean(git(['rev-parse', '--verify', '--quiet', 'HEAD']).trim());
}

function main() {
  if (!hasCommits()) return 0;
  const ref = defaultBranch();
  const base = ref ? git(['merge-base', ref, 'HEAD']).trim() : '';
  if (!base) {
    console.error('could not resolve a merge-base against the default branch - refusing to pass blind.');
    return 1;
  }
  const findings = collect(base);
  findings.forEach((finding) => console.log(finding));
  if (findings.length === 0) return 0;
  const reason = justification(base);
  if (reason) return 0;
  console.error(`${findings.length} assertion-weakening change(s) with no 'test-change-ok: <reason>' justification.`);
  return 1;
}

module.exports = { fileFindings };

if (require.main === module) process.exit(main());

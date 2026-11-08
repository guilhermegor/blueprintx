const { execFileSync } = require('node:child_process');
const fs = require('node:fs');

const RE_TEST_PATH = /\.(test|spec)\.(ts|tsx|js|jsx)$/;
const RE_TEST_START = /(?<![.\w])[fx]?(?:it|test)(?:\.each\((?:[^()]|\([^()]*\))*\)|\.\w+)?\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;
const RE_MATCHER = /\.(not\.)?(to[A-Z]\w*)\(/g;
const RE_PLACEHOLDER = /^<[^>]*>$/;
const RE_JUSTIFICATION = /^\s*test-change-ok:[ \t]*(\S.*)$/im;

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
  return [...body.matchAll(RE_MATCHER)].filter((match) => !match[1]).map((match) => match[2]);
}

function surplus(names, others, allowed) {
  const left = [...others];
  return names
    .filter((name) => allowed.has(name))
    .filter((name) => {
      const index = left.indexOf(name);
      if (index >= 0) left.splice(index, 1);
      return index < 0;
    });
}

function testFindings(path, oldTest, newTest) {
  const oldNames = matchers(oldTest.body);
  const newNames = matchers(newTest.body);
  const removed = surplus(oldNames, newNames, EQUALITY_MATCHERS);
  const added = surplus(newNames, oldNames, INEQUALITY_MATCHERS);
  return removed
    .slice(0, added.length)
    .map((name, index) => `${path}: ${newTest.name}: ${name} loosened to ${added[index]}`);
}

function fileFindings(path, oldSource, newSource) {
  const oldTests = new Map(splitTests(oldSource).map((test) => [test.key, test]));
  return splitTests(newSource)
    .filter((test) => oldTests.has(test.key))
    .flatMap((test) => testFindings(path, oldTests.get(test.key), test));
}

function gitStrict(args) {
  return execFileSync('git', args, {
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
    stdio: ['ignore', 'pipe', 'ignore'],
  });
}

function git(args) {
  try {
    return gitStrict(args);
  } catch {
    return '';
  }
}

function defaultBranch() {
  const fromCi = process.env.GITHUB_BASE_REF ? [`origin/${process.env.GITHUB_BASE_REF}`] : [];
  const candidates = [...fromCi, 'origin/HEAD', 'origin/main', 'origin/master', 'main', 'master'];
  return candidates.find((ref) => git(['rev-parse', '--verify', '--quiet', ref]).trim()) ?? '';
}

function prBody(eventPath) {
  if (!eventPath) return '';
  try {
    return JSON.parse(fs.readFileSync(eventPath, 'utf8')).pull_request?.body ?? '';
  } catch {
    return '';
  }
}

function justification(base) {
  const isCi = Boolean(process.env.CI || process.env.GITHUB_ACTIONS);
  const fromEnv = isCi ? '' : (process.env.TEST_CHANGE_OK ?? '').trim();
  if (fromEnv) return fromEnv;
  const eventPath = process.env.GITHUB_EVENT_PATH;
  const trailers = git(['log', `${base}..HEAD`, '--format=%B']);
  const match = RE_JUSTIFICATION.exec(prBody(eventPath)) ?? RE_JUSTIFICATION.exec(trailers);
  const reason = match ? match[1].trim() : '';
  return RE_PLACEHOLDER.test(reason) ? '' : reason;
}

function changedPaths(output) {
  const tokens = output.split('\0');
  const rows = [];
  for (let index = 0; index < tokens.length - 1; ) {
    const width = /^[RC]/.test(tokens[index]) ? 2 : 1;
    rows.push({ status: tokens[index][0], paths: tokens.slice(index + 1, index + 1 + width) });
    index += width + 1;
  }
  return rows;
}

function collect(base) {
  const output = gitStrict(['diff', '--cached', '-z', '--name-status', '--find-renames', base]);
  const rows = changedPaths(output).filter(
    (row) => !['A', 'D', 'U'].includes(row.status) && RE_TEST_PATH.test(row.paths[row.paths.length - 1]),
  );
  return rows.flatMap((row) => {
    const newPath = row.paths[row.paths.length - 1];
    const oldSource = gitStrict(['show', `${base}:${row.paths[0]}`]);
    const newSource = gitStrict(['show', `:${newPath}`]);
    return fileFindings(newPath, oldSource, newSource);
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
  let findings;
  try {
    findings = collect(base);
  } catch (error) {
    console.error(`git failed while reading the staged diff - refusing to pass blind: ${error.message}`);
    return 1;
  }
  findings.forEach((finding) => console.log(finding));
  if (findings.length === 0) return 0;
  const reason = justification(base);
  if (reason) return 0;
  console.error(`${findings.length} assertion-weakening change(s) with no 'test-change-ok: <reason>' justification.`);
  return 1;
}

module.exports = { fileFindings, collect, justification };

if (require.main === module) process.exit(main());

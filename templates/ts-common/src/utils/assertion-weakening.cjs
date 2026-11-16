const { execFileSync } = require('node:child_process');
const fs = require('node:fs');

const RE_TEST_PATH = /\.(test|spec)\.(ts|tsx|js|jsx)$/;
const RE_TEST_START = /(?<![.\w])[fx]?(?:it|test)(?:\.\w+)*(?:\.each\((?:[^()]|\([^()]*\))*\))?\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;
const RE_EXPECT = /(?<![.\w])expect(?:\.\w+)?\(/g;
const RE_MATCHER_TAIL = /^\s*(?:\.(?:resolves|rejects)\s*)?(\.not\s*)?\.\s*(to[A-Z]\w*)\(/;
const RE_MATCHER_ANYWHERE = /(?:\.(?:resolves|rejects))?(\.not)?\.(to[A-Z]\w*)\(/;
const RE_PLACEHOLDER = /^<[^>]*>$/;
const RE_JUSTIFICATION = /^\s*test-change-ok:[ \t]*(\S.*)$/gim;

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

function skipString(text, from) {
  const quote = text[from];
  let index = from + 1;
  while (index < text.length && text[index] !== quote) index += text[index] === '\\' ? 2 : 1;
  return index;
}

function closingParen(text, from) {
  let depth = 1;
  for (let index = from; index < text.length; index += 1) {
    if ('\'"`'.includes(text[index])) index = skipString(text, index);
    depth += { '(': 1, ')': -1 }[text[index]] ?? 0;
    if (depth === 0) return index;
  }
  return -1;
}

function assertionAt(body, match) {
  const from = match.index + match[0].length;
  const close = closingParen(body, from);
  const tail = close < 0 ? RE_MATCHER_ANYWHERE.exec(body.slice(from)) : RE_MATCHER_TAIL.exec(body.slice(close + 1));
  if (!tail || tail[1]) return null;
  const subject = close < 0 ? '' : body.slice(from, close).replace(/\s+/g, '');
  return { subject, matcher: tail[2] };
}

function matchersBySubject(body) {
  const bySubject = new Map();
  [...body.matchAll(RE_EXPECT)]
    .map((match) => assertionAt(body, match))
    .filter(Boolean)
    .forEach(({ subject, matcher }) => bySubject.set(subject, [...(bySubject.get(subject) ?? []), matcher]));
  return bySubject;
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

function subjectFindings(oldNames, newNames) {
  const removed = surplus(oldNames, newNames, EQUALITY_MATCHERS);
  const added = surplus(newNames, oldNames, INEQUALITY_MATCHERS);
  return removed.slice(0, added.length).map((name, index) => `${name} loosened to ${added[index]}`);
}

function testFindings(path, oldTest, newTest) {
  const oldBySubject = matchersBySubject(oldTest.body);
  const newBySubject = matchersBySubject(newTest.body);
  const shared = [...oldBySubject.keys()].filter((subject) => newBySubject.has(subject));
  const unshared = (bySubject) =>
    [...bySubject].filter(([subject]) => !shared.includes(subject)).flatMap(([, names]) => names);
  return [
    ...shared.flatMap((subject) => subjectFindings(oldBySubject.get(subject), newBySubject.get(subject))),
    ...subjectFindings(unshared(oldBySubject), unshared(newBySubject)),
  ].map((finding) => `${path}: ${newTest.name}: ${finding}`);
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
    stdio: ['ignore', 'pipe', 'pipe'],
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

function mergeHeads() {
  const gitPath = git(['rev-parse', '--git-path', 'MERGE_HEAD']).trim();
  if (!gitPath || !fs.existsSync(gitPath)) return [];
  return fs.readFileSync(gitPath, 'utf8').split(/\s+/).filter(Boolean);
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
  if (fromEnv && !RE_PLACEHOLDER.test(fromEnv)) return fromEnv;
  const eventPath = process.env.GITHUB_EVENT_PATH;
  const trailers = git(['log', `${base}..HEAD`, '--format=%B']);
  const reasons = [prBody(eventPath), trailers].flatMap((text) =>
    [...text.matchAll(RE_JUSTIFICATION)].map((match) => match[1].trim()),
  );
  return reasons.find((reason) => !RE_PLACEHOLDER.test(reason)) ?? '';
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
  gitStrict(['rev-parse', '--git-dir']);
  return Boolean(git(['rev-parse', '--verify', '--quiet', 'HEAD']).trim());
}

function repoHasCommits() {
  try {
    return hasCommits();
  } catch (error) {
    console.error(`git is unusable here - refusing to pass blind: ${error.message}`);
    return null;
  }
}

function main() {
  const committed = repoHasCommits();
  if (committed === null) return 1;
  if (!committed) return 0;
  const ref = defaultBranch();
  const base = ref ? git(['merge-base', ref, 'HEAD', ...mergeHeads()]).trim() : '';
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

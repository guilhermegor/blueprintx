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

  it('ignores a negated matcher swap', () => {
    const negated = "it('computes', () => {\n  expect(x).not.toBe(5);\n});\n";
    expect(fileFindings('a.test.ts', negated, spec('toBeGreaterThan'))).toEqual([]);
  });
});

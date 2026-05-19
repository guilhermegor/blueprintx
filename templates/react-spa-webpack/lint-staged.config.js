/**
 * react-spa-webpack adds CSS handling on top of the ts-common baseline.
 * When lint-staged finds both `lint-staged.config.js` and a `"lint-staged"`
 * field in package.json, the JS file wins. So this is the *complete*
 * config for projects scaffolded with the react-spa-webpack template.
 */
export default {
  '*.{js,jsx,ts,tsx}': ['prettier --write', 'eslint --fix --max-warnings 0'],
  '*.css': ['prettier --write', 'stylelint --fix'],
  '*.{json,md}': ['prettier --write'],
};

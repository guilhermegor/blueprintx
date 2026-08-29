/**
 * ts-lib ships no CSS, so this is the complete config (unlike
 * react-spa-webpack, which adds a stylelint entry on top of the ts-common
 * baseline).
 */
export default {
  '*.ts': ['prettier --write', 'eslint --fix --max-warnings 0'],
  '*.{json,md}': ['prettier --write'],
};

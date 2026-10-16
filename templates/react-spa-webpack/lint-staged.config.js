export default {
  '*.{js,jsx,ts,tsx}': ['prettier --write', 'eslint --fix --max-warnings 0'],
  '*.css': ['prettier --write', 'stylelint --fix'],
  '*.{json,md}': ['prettier --write'],
};

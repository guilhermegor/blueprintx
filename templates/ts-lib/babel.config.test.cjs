// Jest-only Babel config, wired explicitly via jest.config.cjs's `transform` option
// (configFile). Deliberately NOT named `.babelrc` / `babel.config.js` — those filenames
// are auto-discovered by ANY tool that resolves Babel config from the project root,
// including Docusaurus's own webpack/babel-loader pipeline when building `docs/` — which
// broke with "'import'/'export' may appear only with sourceType: module" when a root
// `.babelrc` shadowed Docusaurus's own preset. An explicit, non-discoverable filename
// scopes this config to Jest alone.
module.exports = {
  presets: [['@babel/preset-env', { targets: { node: 'current' } }], '@babel/preset-typescript'],
};

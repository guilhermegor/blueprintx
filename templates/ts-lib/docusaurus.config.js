// @ts-check
// Docusaurus site config for ${PROJECT_NAME}. `${...}` placeholders are rendered via
// envsubst at scaffold time (see bin/scaffold/ts_lib.sh) — do not replace them with
// literal values here. Docs-only mode: blog disabled, docs served at the site root.

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: '${PROJECT_NAME}',
  tagline: '${PROJECT_DESCRIPTION}',
  url: 'https://${GITHUB_USERNAME}.github.io',
  baseUrl: '/${PROJECT_NAME}/',
  organizationName: '${GITHUB_USERNAME}',
  projectName: '${PROJECT_NAME}',
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}/edit/main/docs/',
        },
        blog: false,
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: '${PROJECT_NAME}',
        items: [
          {
            href: 'https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
    }),
};

module.exports = config;

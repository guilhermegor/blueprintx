// @ts-check

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

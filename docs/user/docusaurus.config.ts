import {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'LLM Stack Documentation',
  tagline: 'Self-Hosted LLM & LLMOps Platform User Guide',
  favicon: 'img/favicon.ico',

  url: process.env.DOCS_URL || 'https://docs.local',
  baseUrl: process.env.DOCS_BASE_URL || '/',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'throw',
  onDuplicateRoutes: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'fr'],
    localeConfigs: {
      en: {
        label: 'English',
        direction: 'ltr',
        htmlLang: 'en-US',
      },
      fr: {
        label: 'Français',
        direction: 'ltr',
        htmlLang: 'fr-FR',
      },
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'LLM Stack',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'userSidebar',
          position: 'left',
          label: 'User Guide',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://github.com/jaseran-ai/llm-stack',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Getting Started',
              to: '/getting-started/',
            },
            {
              label: 'Tutorials',
              to: '/tutorials/',
            },
            {
              label: 'How-To Guides',
              to: '/how-to/',
            },
          ],
        },
        {
          title: 'Reference & Concepts',
          items: [
            {
              label: 'Technical Reference',
              to: '/reference/',
            },
            {
              label: 'Explanations',
              to: '/explanation/',
            },
            {
              label: 'Release Notes',
              to: '/release-notes/',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} LLM Stack. Built with Docusaurus.`,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;

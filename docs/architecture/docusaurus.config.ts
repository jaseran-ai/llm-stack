import {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'LLM Stack Architecture Specification',
  tagline: 'Engineering Architecture (arc42, C4 Model, and ADRs) — Internal & Confidential',
  favicon: 'img/favicon.ico',

  url: process.env.DOCS_URL || 'https://arch.local',
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
      title: 'LLM Stack Architecture (arc42 + C4)',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'archSidebar',
          position: 'left',
          label: 'Specification',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Architecture (arc42)',
          items: [
            {
              label: '1. Goals & Requirements',
              to: '/introduction-and-goals',
            },
            {
              label: '5. Building Block View (C4)',
              to: '/building-block-view',
            },
            {
              label: '6. Runtime View (Sequences)',
              to: '/runtime-view',
            },
          ],
        },
        {
          title: 'Decisions & Governance',
          items: [
            {
              label: '9. Architecture Decisions (ADR)',
              to: '/architecture-decisions',
            },
            {
              label: '11. Risks & Technical Debt',
              to: '/risks-and-technical-debt',
            },
            {
              label: '12. Glossary',
              to: '/glossary',
            },
          ],
        },
      ],
      copyright: `Internal & Confidential. Copyright © ${new Date().getFullYear()} LLM Stack Engineering.`,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;

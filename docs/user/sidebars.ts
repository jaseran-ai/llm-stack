import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  userSidebar: [
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: [
        'getting-started/index',
        'getting-started/installation',
      ],
    },
    {
      type: 'category',
      label: 'Tutorials',
      collapsed: false,
      items: [
        'tutorials/index',
        'tutorials/add-an-application',
        'tutorials/consume-api',
      ],
    },
    {
      type: 'category',
      label: 'How-To Guides',
      collapsed: false,
      items: [
        'how-to/index',
        'how-to/authenticate-sso',
        'how-to/backup-and-restore',
        'how-to/configure-web-search',
        'how-to/monitor-traces',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      collapsed: false,
      items: [
        'reference/index',
        'reference/configuration',
        'reference/supported-models',
        'reference/api',
        'reference/error-codes',
      ],
    },
    {
      type: 'category',
      label: 'Explanations',
      collapsed: false,
      items: [
        'explanation/index',
        'explanation/pii-redaction-and-privacy',
        'explanation/zero-trust-model',
      ],
    },
    {
      type: 'category',
      label: 'Release Notes',
      collapsed: false,
      items: [
        'release-notes/index',
        'release-notes/v1.0.0',
      ],
    },
  ],
};

export default sidebars;

import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  archSidebar: [
    {
      type: 'category',
      label: 'Architecture Specification (arc42)',
      collapsed: false,
      items: [
        'introduction-and-goals',
        'architecture-constraints',
        'context-and-scope',
        'solution-strategy',
        'building-block-view',
        'runtime-view',
        'deployment-view',
        'crosscutting-concepts',
        'architecture-decisions',
        'quality-requirements',
        'risks-and-technical-debt',
        'glossary',
      ],
    },
    {
      type: 'category',
      label: 'Decision Records (ADR)',
      collapsed: false,
      items: [
        'adr/authentik-unified-identity-and-rbac',
        'adr/vault-kv-v2-and-tmpfs-memory-secrets',
        'adr/traefik-v3-ingress-and-security-headers',
        'adr/internal-tls-and-local-ca-injection',
        'adr/betterleaks-presidio-redaction-and-redis-tokenization',
        'adr/seaweedfs-least-privilege-s3-iam',
        'adr/multi-tier-network-segmentation',
      ],
    },
  ],
};

export default sidebars;

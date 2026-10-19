# 7. Vue de Déploiement

Cette section décrit l'infrastructure physique et conteneurisée de la stack LLM.

---

## 7.1 Infrastructure & Environnement Hôte

La plateforme s'exécute sur un hôte Linux unique (distribution compatible Debian, Ubuntu ou RHEL) avec Docker Engine et Docker Compose :

* **Système d'exploitation** : Kernel Linux 6.x avec cgroups v2 activés.
* **Architecture de stockage** :
  * **Volumes persistants** : Volumes nommés Docker (`postgres_data`, `clickhouse_data`, `seaweedfs_data`, `qdrant_data`, `vault_data`, `loki_data`) mappés sur le système de fichiers hôte.
  * **Volume mémoire volatile (`tmpfs`)** : Un volume RAM-backed isolé de 64 Mo (`secrets_ram`) monté sur `/vault/secrets_ram` avec permissions `0700` pour le répertoire et `0600` pour les fichiers.
* **Périmètre d'entrée** : Aucun port de routeur entrant n'est requis. L'ensemble du trafic transite par le tunnel `cloudflared` vers Cloudflare Zero Trust.

---

## 7.2 Topologie des Conteneurs

```text
Hôte (Serveur Linux Mononœud)
│
├── Edge Cloudflare Zero Trust (DNS, WAF, min TLS 1.2)
│   └── [Tunnel sortant QUIC / HTTPS]
│
├── Niveau Ingress
│   ├── cloudflared
│   └── traefik (Proxy inverse, :80, :443, :8080 admin, :8082 métriques)
│
├── Sécurité & Identité
│   ├── authentik-server & authentik-worker
│   ├── vault (TLS interne :8200) & vault-agent (rendu tmpfs)
│   └── betterleaks-presidio (:8080 HTTP, :50052 gRPC)
│
├── Applications & Passerelles
│   ├── open-webui (:8080)
│   ├── litellm (:4000)
│   ├── searxng (:8080) & chouse-ui (:5521)
│   └── ollama (:11434 inférence CPU)
│
├── Persistance & Caching
│   ├── postgres (:5432)
│   ├── clickhouse-server (:8123, :9000)
│   ├── seaweedfs (:8888 Filer, :8333 S3)
│   ├── qdrant (:6333)
│   └── redis (:6379)
│
└── Observabilité
    ├── prometheus (:9090) & alertmanager (:9093)
    ├── grafana (:3000)
    ├── vector (écouteur socket) & loki (:3100)
    ├── dozzle (:8080) & gatus (:80)
    └── cadvisor & node-exporter
```

---

## 7.3 Topologie Réseau & Segmentation Multi-Tiers

La stack met en œuvre une architecture multi-réseaux segmentée afin d'appliquer une défense en profondeur et de neutraliser les mouvements latéraux et l'exfiltration de données :

| Nom du Réseau | Driver Docker | Interne / Air-Gapped | Plage de Sous-Réseau | Services Affectés | Objectif & Rôle |
|---|---|---|---|---|---|
| `llm-stack_default` | bridge | Non (Passerelle Sortante) | `172.18.0.0/16` | Traefik, Cloudflared, Open-WebUI, Ollama, Qdrant, SeaweedFS, agents d'observabilité, applications multi-réseaux | Routage edge, trafic utilisateur et connectivité vers les fournisseurs externes. Le provider Docker de Traefik est épinglé sur ce réseau. |
| `llm-stack_backend` | bridge | **Oui (`internal: true`)** | `172.24.0.0/16` | `postgres`, `clickhouse`, `redis` (exclusivement), plus les consommateurs autorisés (`authentik`, `litellm`, `langfuse`, `chouse-ui`, `betterleaks`, `gatus`) | Réseau backend isolé sans passerelle par défaut. Empêche toute exfiltration vers Internet et bloque l'accès latéral depuis les tiers non autorisés. |

---

## 7.4 Portabilité Multi-Arch & Digests

Pour garantir une reproductibilité absolue sur les postes des développeurs (ex: Apple Silicon `linux/arm64`) et les serveurs de production (`linux/amd64`) :
* Chaque service dans `docker-compose.yml` spécifie un digest manifeste multi-architecture immuable (`@sha256:...`).
* Les builds d'images personnalisées (`betterleaks-presidio`) exploitent des Dockerfiles multi-étapes supportant la compilation native sur les deux architectures.


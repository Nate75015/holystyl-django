# Infrastructure Holystyl — Terraform (Scaleway)

Calqué sur le pattern des autres apps (Katarina, document-citoyen) :
une couche **`shared`** crée les fondations partagées (projet Scaleway, bucket de
state, registry Docker), puis des **`envs/<env>`** déploieront l'application
(base PostgreSQL, stockage médias, exécution, DNS).

```
infra/terraform/
├── shared/            ← projet + bucket tfstate + registry   ← PHASE 1 (ici)
└── envs/
    ├── preprod/       ← déploiement preprod                  ← PHASE 2
    └── prod/          ← déploiement prod                     ← PHASE 2
```

## Phase 1 — Fondations (`shared`)

Crée : projet Scaleway `holystyl`, bucket `holystyl-tfstate` (versionné),
registry `holystyl`.

### Identifiants

Le provider Scaleway lit le profil actif de `~/.config/scw/config.yaml`
(ou les variables `SCW_ACCESS_KEY` / `SCW_SECRET_KEY`).

### Bootstrap (state local → distant)

```bash
cd infra/terraform/shared
terraform init
terraform plan        # vérifier : 3 ressources à créer
terraform apply       # crée projet + bucket + registry

# Puis bascule le state dans le bucket :
mv backend.tf.example backend.tf
export AWS_ACCESS_KEY_ID=$(scw config get access-key)
export AWS_SECRET_ACCESS_KEY=$(scw config get secret-key)
terraform init -migrate-state
```

## Phase 2 — Déploiement Kubernetes (Kapsule)

À venir dans `envs/`. Reprend le pattern Kapsule de
`mairie-agglo/platform/terraform` :
- `scaleway_k8s_cluster` + `scaleway_k8s_pool`
- base `scaleway_rdb_instance` (PostgreSQL) + `scaleway_object_bucket` médias
- manifests Kubernetes (Deployment/Service/Ingress) consommant l'image
  poussée sur le registry `holystyl`.

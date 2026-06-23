provider "scaleway" {
  organization_id = var.scaleway_organization_id
  project_id      = var.project_id
  region          = var.scaleway_region
  zone            = var.scaleway_zone
}

# ──────────────────────────────────────────────────────────────────────────────
# Réseau privé (VPC) — réseau du cluster Kapsule.
# ──────────────────────────────────────────────────────────────────────────────
resource "scaleway_vpc" "this" {
  name       = "${var.cluster_name}-vpc"
  project_id = var.project_id
  region     = var.scaleway_region
}

resource "scaleway_vpc_private_network" "this" {
  name       = "${var.cluster_name}-pn"
  vpc_id     = scaleway_vpc.this.id
  project_id = var.project_id
  region     = var.scaleway_region
}

# ──────────────────────────────────────────────────────────────────────────────
# Cluster Kapsule (control plane managé — gratuit hors offre Dedicated)
# ──────────────────────────────────────────────────────────────────────────────
resource "scaleway_k8s_cluster" "this" {
  name                        = var.cluster_name
  project_id                  = var.project_id
  region                      = var.scaleway_region
  version                     = var.kubernetes_version
  cni                         = "cilium"
  description                 = "Cluster Kapsule Holystyl — preprod"
  delete_additional_resources = true
  private_network_id          = scaleway_vpc_private_network.this.id

  auto_upgrade {
    enable                        = false
    maintenance_window_start_hour = 3
    maintenance_window_day        = "sunday"
  }
}

resource "scaleway_k8s_pool" "default" {
  cluster_id  = scaleway_k8s_cluster.this.id
  name        = "default"
  node_type   = var.node_type
  size        = var.pool_size
  min_size    = var.pool_min_size
  max_size    = var.pool_max_size
  autoscaling = true
  autohealing = true
  zone        = var.scaleway_zone
}

# ──────────────────────────────────────────────────────────────────────────────
# PostgreSQL — Serverless SQL (hors quota RDB, scale-to-zero).
# Accès via endpoint public + clé IAM dédiée (pas de réseau privé).
# ──────────────────────────────────────────────────────────────────────────────
resource "scaleway_sdb_sql_database" "this" {
  name       = var.db_name
  project_id = var.project_id
  region     = var.scaleway_region
  min_cpu    = 0
  max_cpu    = var.serverless_sql_max_cpu
}

# Application IAM + clé API dédiées : identifiants applicatifs de la base.
resource "scaleway_iam_application" "db" {
  name        = "${var.cluster_name}-db"
  description = "Holystyl preprod — accès Serverless SQL"
}

resource "scaleway_iam_policy" "db" {
  name           = "${var.cluster_name}-db-rw"
  description    = "Lecture/écriture Serverless SQL pour Holystyl preprod"
  application_id = scaleway_iam_application.db.id

  rule {
    project_ids          = [var.project_id]
    permission_set_names = ["ServerlessSQLDatabaseReadWrite"]
  }
}

resource "scaleway_iam_api_key" "db" {
  application_id = scaleway_iam_application.db.id
  description    = "Holystyl preprod — Serverless SQL"
}

# ──────────────────────────────────────────────────────────────────────────────
# Bucket Object Storage pour les médias Django
# ──────────────────────────────────────────────────────────────────────────────
resource "scaleway_object_bucket" "media" {
  name       = var.media_bucket_name
  project_id = var.project_id
  region     = var.scaleway_region
}

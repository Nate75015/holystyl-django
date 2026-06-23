provider "scaleway" {
  organization_id = var.scaleway_organization_id
  project_id      = var.project_id
  region          = var.scaleway_region
  zone            = var.scaleway_zone
}

# ──────────────────────────────────────────────────────────────────────────────
# Réseau privé (VPC) — Kapsule et PostgreSQL partagent le même réseau privé,
# les pods accèdent à la base sans passer par Internet ni un LB facturé.
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
# PostgreSQL managé (endpoint privé sur le VPC du cluster)
# ──────────────────────────────────────────────────────────────────────────────
resource "random_password" "db_admin" {
  length           = 32
  special          = true
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "!#$%&*+-_="
}

resource "random_password" "db_app" {
  length           = 32
  special          = true
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "!#$%&*+-_="
}

resource "scaleway_rdb_instance" "this" {
  name                      = "${var.cluster_name}-db"
  project_id                = var.project_id
  region                    = var.scaleway_region
  node_type                 = var.postgres_node_type
  engine                    = "PostgreSQL-16"
  user_name                 = "holystyl_admin"
  password                  = random_password.db_admin.result
  volume_size_in_gb         = var.postgres_volume_size_gb
  volume_type               = "sbs_5k"
  disable_backup            = false
  backup_schedule_frequency = 24
  backup_schedule_retention = 7

  private_network {
    pn_id       = scaleway_vpc_private_network.this.id
    enable_ipam = true
  }
}

resource "scaleway_rdb_database" "app" {
  instance_id = scaleway_rdb_instance.this.id
  name        = var.db_name
}

resource "scaleway_rdb_user" "app" {
  instance_id = scaleway_rdb_instance.this.id
  name        = var.db_user
  password    = random_password.db_app.result
  is_admin    = false
}

resource "scaleway_rdb_privilege" "app" {
  instance_id   = scaleway_rdb_instance.this.id
  database_name = scaleway_rdb_database.app.name
  user_name     = scaleway_rdb_user.app.name
  permission    = "all"

  depends_on = [scaleway_rdb_database.app, scaleway_rdb_user.app]
}

# ──────────────────────────────────────────────────────────────────────────────
# Bucket Object Storage pour les médias Django
# ──────────────────────────────────────────────────────────────────────────────
resource "scaleway_object_bucket" "media" {
  name       = var.media_bucket_name
  project_id = var.project_id
  region     = var.scaleway_region
}

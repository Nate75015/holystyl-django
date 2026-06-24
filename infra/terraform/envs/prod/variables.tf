variable "scaleway_organization_id" {
  type = string
}

variable "project_id" {
  description = "ID du projet Scaleway Holystyl (output `project_id` de la couche shared)."
  type        = string
}

variable "scaleway_region" {
  type    = string
  default = "fr-par"
}

variable "scaleway_zone" {
  type    = string
  default = "fr-par-1"
}

# ── Kapsule ───────────────────────────────────────────────────────────────────
variable "cluster_name" {
  type    = string
  default = "holystyl-prod"
}

variable "kubernetes_version" {
  type    = string
  default = "1.34.6"
}

variable "node_type" {
  type    = string
  default = "PRO2-XXS"
}

variable "pool_size" {
  type    = number
  default = 2
}

variable "pool_min_size" {
  type    = number
  default = 2
}

variable "pool_max_size" {
  type    = number
  default = 4
}

# ── PostgreSQL managé (RDB) ───────────────────────────────────────────────────
variable "postgres_node_type" {
  type    = string
  default = "db-dev-s"
}

variable "postgres_volume_size_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "holystyl"
}

variable "db_user" {
  type    = string
  default = "holystyl_app"
}

# ── Stockage médias ───────────────────────────────────────────────────────────
variable "media_bucket_name" {
  type    = string
  default = "holystyl-media-prod"
}

variable "scaleway_organization_id" {
  description = "Scaleway organization ID."
  type        = string
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
  default = "holystyl-preprod"
}

variable "kubernetes_version" {
  type    = string
  default = "1.34.6"
}

variable "node_type" {
  description = "Type d'Instance Scaleway pour les nœuds du pool."
  type        = string
  default     = "PRO2-XXS"
}

variable "pool_size" {
  type    = number
  default = 1
}

variable "pool_min_size" {
  type    = number
  default = 1
}

variable "pool_max_size" {
  type    = number
  default = 3
}

# ── PostgreSQL ────────────────────────────────────────────────────────────────
variable "postgres_node_type" {
  type    = string
  default = "db-dev-s"
}

variable "postgres_volume_size_gb" {
  type    = number
  default = 10
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
  description = "Bucket Object Storage des médias (globalement unique)."
  type        = string
  default     = "holystyl-media-preprod"
}

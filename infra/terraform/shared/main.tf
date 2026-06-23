provider "scaleway" {
  organization_id = var.scaleway_organization_id
  region          = var.scaleway_region
  zone            = var.scaleway_zone
}

# ── Projet Scaleway dédié ─────────────────────────────────────────────────────
resource "scaleway_account_project" "holystyl" {
  name        = var.project_name
  description = "Holystyl — agri-tech : gestion d'exploitation agricole (Django)"
}

# ── Bucket Object Storage pour le state Terraform distant ─────────────────────
# Volontairement créé dans le projet par défaut de l'organisation : la clé IAM
# utilisée localement est scopée au projet par défaut, donc seule cette
# localisation est accessible en lecture/écriture S3.
resource "scaleway_object_bucket" "tfstate" {
  name   = var.tfstate_bucket_name
  region = var.scaleway_region

  versioning {
    enabled = true
  }
}

# ── Container Registry partagé entre preprod et prod ──────────────────────────
resource "scaleway_registry_namespace" "holystyl" {
  name        = var.registry_namespace
  description = "Images Docker Django Holystyl"
  region      = var.scaleway_region
  project_id  = scaleway_account_project.holystyl.id
  is_public   = false
}

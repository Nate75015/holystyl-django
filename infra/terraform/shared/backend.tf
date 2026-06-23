# Backend S3 (Scaleway Object Storage) pour le state distant.
#
# ⚠️ Bootstrap : le bucket "holystyl-tfstate" est CRÉÉ par cette même couche
# `shared`. On ne peut donc pas activer ce backend au premier apply (le bucket
# n'existe pas encore). Procédure :
#
#   1. Premier apply en state LOCAL (sans ce fichier) → crée projet + bucket + registry.
#   2. Renommer ce fichier en `backend.tf`.
#   3. `terraform init -migrate-state` (répondre "yes") pour pousser le state dans le bucket.
#
# Identifiants S3 attendus par le backend (clés Scaleway) :
#   export AWS_ACCESS_KEY_ID=$(scw config get access-key)
#   export AWS_SECRET_ACCESS_KEY=$(scw config get secret-key)

terraform {
  backend "s3" {
    bucket   = "holystyl-tfstate"
    key      = "shared/terraform.tfstate"
    region   = "fr-par"
    endpoint = "https://s3.fr-par.scw.cloud"

    skip_credentials_validation = true
    skip_region_validation      = true
    skip_metadata_api_check     = true
    force_path_style            = true
  }
}

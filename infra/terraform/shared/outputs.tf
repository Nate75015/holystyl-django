output "project_id" {
  description = "ID du projet Scaleway dédié à Holystyl, à passer aux modules envs."
  value       = scaleway_account_project.holystyl.id
}

output "project_name" {
  value = scaleway_account_project.holystyl.name
}

output "tfstate_bucket" {
  description = "Bucket à utiliser dans le backend S3 des envs (envs/*/backend.tf)."
  value       = scaleway_object_bucket.tfstate.name
}

output "tfstate_endpoint" {
  description = "Endpoint S3 Scaleway pour le backend."
  value       = "https://s3.${var.scaleway_region}.scw.cloud"
}

output "registry_endpoint" {
  description = "Hôte du registry à utiliser dans les images Docker (rg.fr-par.scw.cloud/<ns>)."
  value       = scaleway_registry_namespace.holystyl.endpoint
}

output "registry_namespace" {
  value = scaleway_registry_namespace.holystyl.name
}

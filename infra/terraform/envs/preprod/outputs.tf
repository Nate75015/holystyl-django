output "cluster_id" {
  value = scaleway_k8s_cluster.this.id
}

output "cluster_name" {
  value = scaleway_k8s_cluster.this.name
}

output "kubeconfig" {
  description = "Kubeconfig du cluster (sensible)."
  value       = scaleway_k8s_cluster.this.kubeconfig[0].config_file
  sensitive   = true
}

output "cluster_url" {
  value = scaleway_k8s_cluster.this.apiserver_url
}

output "rdb_endpoint_ip" {
  description = "IP privée de l'instance PostgreSQL (réseau privé)."
  value       = try(scaleway_rdb_instance.this.private_network[0].ip, null)
}

output "rdb_database" {
  value = scaleway_rdb_database.app.name
}

output "rdb_user" {
  value = scaleway_rdb_user.app.name
}

output "rdb_password" {
  description = "Mot de passe de l'utilisateur applicatif (sensible)."
  value       = random_password.db_app.result
  sensitive   = true
}

output "media_bucket" {
  value = scaleway_object_bucket.media.name
}

output "registry_endpoint" {
  value = "rg.${var.scaleway_region}.scw.cloud/holystyl"
}

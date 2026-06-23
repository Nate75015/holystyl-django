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

output "db_endpoint" {
  description = "Endpoint de connexion Serverless SQL (host:port/db)."
  value       = scaleway_sdb_sql_database.this.endpoint
}

output "db_name" {
  value = scaleway_sdb_sql_database.this.name
}

output "db_access_key" {
  description = "Access key IAM pour la connexion (= user PostgreSQL, sensible)."
  value       = scaleway_iam_api_key.db.access_key
  sensitive   = true
}

output "db_secret_key" {
  description = "Secret key IAM pour la connexion (= password PostgreSQL, sensible)."
  value       = scaleway_iam_api_key.db.secret_key
  sensitive   = true
}

output "media_bucket" {
  value = scaleway_object_bucket.media.name
}

output "registry_endpoint" {
  value = "rg.${var.scaleway_region}.scw.cloud/holystyl"
}

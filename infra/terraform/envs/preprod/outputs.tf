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

output "media_bucket" {
  value = scaleway_object_bucket.media.name
}

output "registry_endpoint" {
  value = "rg.${var.scaleway_region}.scw.cloud/holystyl"
}

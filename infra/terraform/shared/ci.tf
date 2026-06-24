# Identité CI/CD dédiée (GitHub Actions) — clé API scopée au projet holystyl :
# push d'images sur le registry + accès Kubernetes (récupération du kubeconfig).
resource "scaleway_iam_application" "ci" {
  name        = "holystyl-ci"
  description = "CI/CD GitHub Actions — build & deploy"
}

resource "scaleway_iam_policy" "ci" {
  name           = "holystyl-ci"
  description    = "Push registry + accès Kubernetes pour GitHub Actions"
  application_id = scaleway_iam_application.ci.id

  rule {
    project_ids          = [scaleway_account_project.holystyl.id]
    permission_set_names = ["ContainerRegistryFullAccess", "KubernetesFullAccess"]
  }
}

resource "scaleway_iam_api_key" "ci" {
  application_id     = scaleway_iam_application.ci.id
  default_project_id = scaleway_account_project.holystyl.id
  description        = "GitHub Actions CI — Holystyl"
}

output "ci_access_key" {
  description = "Access key de la clé CI (à mettre dans le secret GitHub SCW_ACCESS_KEY)."
  value       = scaleway_iam_api_key.ci.access_key
  sensitive   = true
}

output "ci_secret_key" {
  description = "Secret key de la clé CI (à mettre dans le secret GitHub SCW_SECRET_KEY)."
  value       = scaleway_iam_api_key.ci.secret_key
  sensitive   = true
}

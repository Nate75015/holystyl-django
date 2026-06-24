scaleway_organization_id = "494f821f-b9db-4f80-811d-c7cfdcaf5163"
project_id               = "fd825f3b-363a-4d5f-aeed-edf9ad09de92"
scaleway_region          = "fr-par"
scaleway_zone            = "fr-par-1"

cluster_name       = "holystyl-prod"
kubernetes_version = "1.34.6"
node_type          = "PRO2-XXS"
pool_size          = 2
pool_min_size      = 2
pool_max_size      = 4

postgres_node_type      = "db-dev-s"
postgres_volume_size_gb = 20
db_name                 = "holystyl"
db_user                 = "holystyl_app"

media_bucket_name = "holystyl-media-prod"

# Déploiement Kubernetes — Holystyl preprod (Kapsule)

Cluster provisionné par `infra/terraform/envs/preprod`. Image construite depuis
le `Dockerfile` racine et poussée sur `rg.fr-par.scw.cloud/holystyl`.

## Pré-requis
```bash
# Kubeconfig depuis Terraform
cd infra/terraform/envs/preprod
export AWS_ACCESS_KEY_ID=$(scw config get access-key)
export AWS_SECRET_ACCESS_KEY=$(scw config get secret-key)
terraform output -raw kubeconfig > /tmp/holystyl.kubeconfig
export KUBECONFIG=/tmp/holystyl.kubeconfig
```

## 1. Composants cluster (Helm)
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add jetstack https://charts.jetstack.io && helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer
helm upgrade --install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace --set crds.enabled=true
```
Récupérer l'IP publique du LoadBalancer :
```bash
kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```
Domaine preprod = `<IP>.nip.io` (ou un vrai domaine pointé en A sur cette IP).

## 2. Secrets (valeurs réelles, non committées)
PREPROD utilise **SQLite** (volume persistant `/app/data`, cf. `pvc.yaml`) — pas de base externe.
```bash
kubectl apply -f infra/k8s/preprod/namespace.yaml

# Pull secret registry privé
kubectl -n holystyl create secret docker-registry scw-registry \
  --docker-server=rg.fr-par.scw.cloud --docker-username=nologin \
  --docker-password=$(scw config get secret-key)

# Env applicatif (DATABASE_URL = SQLite sur le volume persistant)
kubectl -n holystyl create secret generic holystyl-env \
  --from-literal=DJANGO_ENV=prod \
  --from-literal=SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(50))') \
  --from-literal=ALLOWED_HOSTS=<HOST> \
  --from-literal=CSRF_TRUSTED_ORIGINS=https://<HOST> \
  --from-literal=DATABASE_URL=sqlite:////app/data/db.sqlite3 \
  --from-literal=REDIS_URL=redis://redis:6379/2 \
  --from-literal=CELERY_BROKER_URL=redis://redis:6379/0 \
  --from-literal=CELERY_RESULT_BACKEND=redis://redis:6379/1 \
  --from-literal=SECURE_SSL_REDIRECT=false
```

## 3. Application
```bash
kubectl apply -f infra/k8s/preprod/pvc.yaml
kubectl apply -f infra/k8s/preprod/redis.yaml
kubectl apply -f infra/k8s/preprod/web.yaml
kubectl apply -f infra/k8s/preprod/cluster-issuer.yaml
sed "s/__HOST__/<HOST>/g" infra/k8s/preprod/ingress.yaml | kubectl apply -f -
```

## Notes
- **Base de données** : preprod = **SQLite** (volume `holystyl-data`, PVC 2Gi). La **prod**
  utilisera **PostgreSQL RDB managé** (`infra/terraform/envs/prod`, à appliquer une fois le
  quota RDB relevé), avec un `DATABASE_URL` `postgres://…` sur le réseau privé.
- Les **probes** envoient un header `Host: <HOST>` (sinon `DisallowedHost` car le kubelet
  interroge via l'IP du pod, absente d'`ALLOWED_HOSTS`).
- **Celery** (worker/beat) non déployé ici — à ajouter si jobs planifiés requis.
- `SECURE_SSL_REDIRECT=false` le temps du 1er test HTTP ; l'ingress redirige déjà HTTP→HTTPS.

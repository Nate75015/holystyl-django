# ── Stage 1 : build des wheels ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libffi-dev libpq-dev \
        git openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# La dép privée satkaar/agenda est clonée en SSH via une deploy key read-only,
# fournie par le CI en secret BuildKit (secret d'org AGENDA_DEPLOY_KEY). La clé
# ne vit que dans ce stage builder (jeté ensuite) — aucune fuite dans l'image.
RUN --mount=type=secret,id=ssh_key \
    pip install --no-cache-dir --upgrade pip \
    && mkdir -p /root/.ssh && chmod 700 /root/.ssh \
    && ssh-keyscan -t ed25519,rsa github.com >> /root/.ssh/known_hosts 2>/dev/null \
    && if [ -s /run/secrets/ssh_key ]; then \
         cp /run/secrets/ssh_key /root/.ssh/id_agenda && chmod 600 /root/.ssh/id_agenda \
         && printf 'Host github.com\n  IdentityFile /root/.ssh/id_agenda\n  IdentitiesOnly yes\n' >> /root/.ssh/config; \
       fi \
    && pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# ── Stage 2 : image finale ────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=prod \
    PORT=8080

WORKDIR /app

# Dépendances système runtime : libpq (Postgres) + pile WeasyPrint (PDF).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libcairo2 libffi8 libharfbuzz0b fontconfig shared-mime-info fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/*

COPY . .
RUN chmod +x entrypoint.sh

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]

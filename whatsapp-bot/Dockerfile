# --- Stage 1: build the React/Vite dashboard -------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /src
COPY frontend-src/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend-src/ ./
RUN npm run build

# --- Stage 2: the actual runtime image --------------------------------------
FROM evoapicloud/evolution-api:v2.3.7

USER root
WORKDIR /evolution

RUN apk add --no-cache bash curl redis postgresql postgresql-client postgresql-contrib python3 py3-pip py3-virtualenv     && apk add --no-cache --virtual .build-deps build-base python3-dev musl-dev postgresql-dev     && python3 -m venv /venv     && /venv/bin/pip install --no-cache-dir --upgrade pip

COPY backend/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt     && apk del .build-deps     && npm install --omit=dev --no-audit --no-fund --save-exact baileys@7.0.0-rc13

COPY backend/app /app/app
COPY --from=frontend-build /frontend /app/frontend
COPY migrations /app/migrations
COPY start-all.sh /app/start-all.sh

RUN chmod +x /app/start-all.sh

EXPOSE 8000
ENTRYPOINT ["/bin/bash", "/app/start-all.sh"]

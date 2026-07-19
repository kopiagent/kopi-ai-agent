# Deploying Kopi Agent on Kubernetes

## Build & push the image

```bash
docker build -t <registry>/kopi-agent:<tag> .
docker push <registry>/kopi-agent:<tag>
```

Then set that image (and a pinned tag — avoid `latest` for customers) in
`kopi.yaml`, change the `api-server-key` in the Secret, and:

```bash
kubectl apply -f deploy/k8s/kopi.yaml
kubectl get pods -l app=kopi -w
```

## What's in the manifest

One pod, two containers sharing one `ReadWriteOnce` PVC mounted at
`/opt/data` (`KOPI_HOME`) — the same layout as `docker-compose.yml`, where
both services share `~/.kopi`.

| Container | Port | Probe endpoints |
|---|---|---|
| gateway | 8642 | `GET /health` (startup/liveness/readiness, no auth) |
| dashboard | 9119 | `GET /api/healthz` (liveness), `GET /api/readyz` (readiness) |

- `/api/healthz` is constant-time and dependency-free — safe as liveness.
  Do **not** use `/api/status` for liveness: it awaits a remote gateway
  health probe and can be slow when the gateway is degraded.
- `/api/readyz` fails (503 + problem list) if the built web bundle is
  missing or `KOPI_HOME` isn't writable — the two realistic "pod is up but
  can't serve" failure modes after a fresh PVC mount or UID remap.
- The gateway only opens :8642 when `API_SERVER_HOST` is set; the manifest
  sets it so HTTP probes work. To run without the API server, remove those
  env vars and switch the gateway probes to the commented `pgrep` exec form.
- Optional extra listener: the webhook server (`:8644`, `GET /health`) if
  you enable webhook subscriptions.

## Per-customer isolation & path routing

The multi-customer pattern is **one namespace per customer**:

```bash
kubectl create namespace cust-acme
kubectl apply -n cust-acme -f deploy/k8s/kopi.yaml
kubectl apply -n cust-acme -f deploy/k8s/ingress-per-customer.yaml  # path /i/acme
```

- Each namespace gets its **own PVC** (its own DO Volume on DOKS) — every
  container mounts it at `/opt/data`, but the disks are physically separate,
  so customer data can never mix. Never use `hostPath` volumes.
- `ingress-per-customer.yaml` routes `https://<host>/i/<customer>/...` to
  that namespace's Service, strips the prefix, and injects
  `X-Forwarded-Prefix` so the dashboard SPA works under the sub-path
  (already supported by `mount_spa()` — no rebuild).
- For DigitalOcean Container Registry (DOCR), pin the image to
  `registry.digitalocean.com/<registry>/kopi-agent:<tag>` and run
  `doctl kubernetes cluster registry attach <registry> <cluster>` once —
  it wires the pull secret into the cluster for you (per-namespace copies
  may be needed for customer namespaces; see DO docs).

## Constraints to know before handing this to customers

- **replicas must stay 1** and the strategy is `Recreate`: all state is one
  PVC; there is no multi-writer coordination.
- **s6-overlay `/init` starts as root** (remaps UID/GID via
  `KOPI_UID`/`KOPI_GID`, chowns the volume, then drops privileges per
  service). Pod-level `runAsNonRoot: true` will break startup; keep the
  privilege drop inside the image.
- **Expose via Ingress with TLS.** The dashboard binds 0.0.0.0 inside the
  pod; non-loopback binds enforce its auth gate, and the probe paths are on
  the no-auth allowlist. Never expose :9119 directly without TLS.
- The image bundles `docker-cli` for optional docker-socket features — do
  not mount the node's Docker socket in customer clusters.
- First boot on an empty PVC seeds config via the image's cont-init hooks;
  give the startupProbe window (3–5 min) before expecting readiness.

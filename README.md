# sentia-dashboard

Arrakeen cluster dashboard — live view of the lab.

## Structure

- `index.html` — frontend, served via nginx ConfigMap
- `api/main.py` — FastAPI backend, reads live data from the Kubernetes API

## Backend

The dashboard API runs as a pod in `sietch-sentia` with a ServiceAccount that has read access to nodes and events. It exposes:

- `GET /api/status` — node statuses + recent events
- `GET /api/health` — health check

## Deployment

Both frontend and backend are deployed as Kubernetes ConfigMaps + Deployments in the `sietch-sentia` namespace on Arrakeen (Raspberry Pi control plane).

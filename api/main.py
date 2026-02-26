#!/usr/bin/env python3
"""
Sentia Dashboard API
Serves live cluster status data via REST API
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kubernetes import client, config
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentia Dashboard API")

# Enable CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load in-cluster k8s config
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes config")
except:
    logger.warning("Failed to load in-cluster config, trying local kubeconfig")
    config.load_kube_config()

v1 = client.CoreV1Api()

# Node definitions
NODES = {
    "arrakeen": {"role": "Control Plane", "arch": "ARM64", "ip": "192.168.1.200"},
    "caladan": {"role": "Worker (GPU)", "arch": "x86_64", "ip": "192.168.1.201"},
    "sietch-tabr": {"role": "Worker (GPU)", "arch": "x86_64", "ip": "192.168.1.202"},
}


def get_node_status(node_name: str) -> dict:
    """Get current status of a k8s node"""
    try:
        node = v1.read_node(node_name)
        
        # Check node conditions
        ready = False
        last_transition = None
        for condition in node.status.conditions:
            if condition.type == "Ready":
                ready = condition.status == "True"
                last_transition = condition.last_transition_time
                break
        
        last_heartbeat = node.status.conditions[0].last_heartbeat_time if node.status.conditions else None
        
        return {
            "name": node_name,
            "status": "online" if ready else "offline",
            "ready": ready,
            "last_seen": last_heartbeat.isoformat() if last_heartbeat else None,
            "last_transition": last_transition.isoformat() if last_transition else None,
            "info": node.status.node_info.to_dict() if node.status.node_info else {},
        }
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {
                "name": node_name,
                "status": "offline",
                "ready": False,
                "last_seen": None,
                "error": "Node not found in cluster",
            }
        raise
    except Exception as e:
        logger.error(f"Error fetching node {node_name}: {e}")
        return {
            "name": node_name,
            "status": "unknown",
            "ready": False,
            "error": str(e),
        }


def get_recent_events(limit: int = 10) -> list:
    """Get recent cluster events relevant to our nodes"""
    try:
        events = v1.list_event_for_all_namespaces(limit=limit)
        
        relevant_events = []
        for event in events.items:
            if any(node in (event.involved_object.name or "").lower() for node in NODES.keys()):
                relevant_events.append({
                    "timestamp": event.last_timestamp.isoformat() if event.last_timestamp else event.metadata.creation_timestamp.isoformat(),
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "object": event.involved_object.name,
                })
        
        # Sort by timestamp descending
        relevant_events.sort(key=lambda x: x["timestamp"], reverse=True)
        return relevant_events[:limit]
    
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []


@app.get("/api/status")
async def get_status():
    """Get full cluster status"""
    nodes_status = []
    
    for node_name, node_info in NODES.items():
        status = get_node_status(node_name)
        nodes_status.append({
            **status,
            **node_info,
        })
    
    events = get_recent_events(limit=15)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes_status,
        "events": events,
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

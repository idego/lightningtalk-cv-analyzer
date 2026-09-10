from __future__ import annotations

import os
from pathlib import Path

import yaml

_REPO_ROOT_ENV = os.environ.get("CV_VALIDATOR_REPO_ROOT")
ROOT = Path(_REPO_ROOT_ENV) if _REPO_ROOT_ENV else Path(__file__).resolve().parents[3]


def test_nonroot_upgrade_prepares_existing_volumes_before_database_users_start():
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    initializer = services["volume-init"]
    assert initializer["user"] == "0:0"
    assert "cv_validator_data:/api-data" in initializer["volumes"]
    assert "web_auth_data:/web-data" in initializer["volumes"]
    assert "chown -R app:app /api-data" in initializer["command"][0]
    assert "chown -R 1000:1000 /web-data" in initializer["command"][0]
    assert "geonames_data:/reference-data" in initializer["volumes"]
    assert "chmod -R a+rX /reference-data" in initializer["command"][0]
    for name in ("api", "feedback-init"):
        assert services[name]["depends_on"]["volume-init"]["condition"] == "service_completed_successfully"
    assert "USER app" in (ROOT / "apps/api/Dockerfile").read_text()
    assert "--uid 10001" in (ROOT / "apps/api/Dockerfile").read_text()
    assert "USER node" in (ROOT / "apps/web/Dockerfile").read_text()


def test_consolidation_keeps_deployment_port_and_private_api_contract():
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    assert services["web"]["environment"]["PORT"] == "3000"
    assert services["web"]["ports"] == ["${WEB_HOST:-127.0.0.1}:${WEB_PORT:-3001}:3000"]
    assert "ports" not in services["api"]
    assert "CV_VALIDATOR_LEGACY_OWNER_SECRET" in services["api"]["environment"]
    assert services["api"]["environment"]["CV_VALIDATOR_INTERNAL_API_SECRET"] == "${INTERNAL_API_SECRET:-}"
    assert services["web"]["environment"]["INTERNAL_API_SECRET"] == "${INTERNAL_API_SECRET:-}"
    lock = dict(line.split("=", 1) for line in (ROOT / "config/geonames.lock").read_text().splitlines())
    assert services["geonames-init"]["environment"]["GEONAMES_SNAPSHOT_VERSION"] == "${GEONAMES_SNAPSHOT_VERSION:-" + lock["version"] + "}"

"""Full integration test for genesis-saas backend."""

import asyncio
import os

os.environ["GENESIS_DATABASE_URL"] = "sqlite+aiosqlite:///test_int.db"
os.environ["GENESIS_DEBUG"] = "true"


async def main():
    # Remove old test db
    if os.path.exists("test_int.db"):
        os.remove("test_int.db")

    from genesis.main import app
    from genesis.db.session import engine
    from genesis.db.models import Base
    from httpx import AsyncClient, ASGITransport

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Health
        r = await c.get("/health")
        assert r.status_code == 200, f"health: {r.status_code}"
        print("GET /health OK")

        # Register
        r = await c.post("/api/v1/auth/register", json={
            "tenant_name": "Acme", "tenant_slug": "acme",
            "email": "admin@acme.com", "password": "pw", "name": "Admin"
        })
        assert r.status_code == 200, f"register: {r.text}"
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        print("POST /auth/register OK")

        # Login
        r = await c.post("/api/v1/auth/login", json={
            "email": "admin@acme.com", "password": "pw", "tenant_slug": "acme"
        })
        assert r.status_code == 200
        print("POST /auth/login OK")

        # Me
        r = await c.get("/api/v1/auth/me", headers=h)
        assert r.status_code == 200
        assert r.json()["name"] == "Admin"
        print("GET /auth/me OK")

        # Create factory
        r = await c.post("/api/v1/factories", json={
            "name": "Healthcare", "domain": "healthcare", "tech_stack": "Python/FastAPI"
        }, headers=h)
        assert r.status_code == 201
        fid = r.json()["id"]
        print(f"POST /factories OK (id={fid[:8]})")

        # List factories
        r = await c.get("/api/v1/factories", headers=h)
        assert r.json()["total"] == 1
        print("GET /factories OK (total=1)")

        # Get factory
        r = await c.get(f"/api/v1/factories/{fid}", headers=h)
        assert r.status_code == 200
        print("GET /factories/:id OK")

        # Update factory
        r = await c.patch(f"/api/v1/factories/{fid}", json={"description": "Updated"}, headers=h)
        assert r.status_code == 200
        print("PATCH /factories/:id OK")

        # Create build
        r = await c.post("/api/v1/builds", json={
            "factory_id": fid, "feature_request": "Add patient scheduling"
        }, headers=h)
        assert r.status_code == 201
        bid = r.json()["id"]
        assert r.json()["status"] == "requirements"
        print(f"POST /builds OK (id={bid[:8]}, status=requirements)")

        # Get build (detail)
        r = await c.get(f"/api/v1/builds/{bid}", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert "requirements_data" in data
        assert "plan" in data
        assert "findings" in data
        assert "file_map" in data
        print("GET /builds/:id OK (full detail)")

        # List builds
        r = await c.get(f"/api/v1/builds?factory_id={fid}", headers=h)
        assert r.json()["total"] == 1
        print("GET /builds?factory_id OK")

        # Activities
        r = await c.get(f"/api/v1/builds/{bid}/activities", headers=h)
        assert r.status_code == 200
        assert len(r.json()) >= 1
        print(f"GET /builds/:id/activities OK ({len(r.json())} activities)")

        # Filemap
        r = await c.get(f"/api/v1/builds/{bid}/filemap", headers=h)
        assert r.status_code == 200
        print("GET /builds/:id/filemap OK")

        # Approve (should fail - not at gate)
        r = await c.post(f"/api/v1/builds/{bid}/approve", json={
            "type": "requirements", "decision": "approved"
        }, headers=h)
        assert r.status_code == 400
        print("POST /builds/:id/approve (gate check) OK")

        # Supervisor status
        r = await c.get("/api/v1/supervisor/status", headers=h)
        assert r.status_code == 200
        sup = r.json()
        print(f"GET /supervisor/status OK (active={sup['active_builds']}, total={sup['total_builds']})")

        # Supervisor active
        r = await c.get("/api/v1/supervisor/active", headers=h)
        assert r.status_code == 200
        print(f"GET /supervisor/active OK ({len(r.json())} builds)")

        # Count all routes
        r = await c.get("/openapi.json")
        routes = sorted(r.json()["paths"].keys())
        print(f"\n{len(routes)} API routes:")
        for route in routes:
            methods = [m.upper() for m in r.json()["paths"][route]]
            print(f"  {' '.join(methods):10s} {route}")

    # Test supervisor module directly
    from genesis.supervisor.supervisor import Supervisor, BuildJob, BuildPriority
    sup = Supervisor("test-tenant", max_concurrent=3, cost_limit_usd=50.0)
    status = sup.get_status()
    assert status["max_concurrent"] == 3
    assert status["has_budget"] is True
    assert len(status["slots"]) == 3
    print(f"\nSupervisor: {status['max_concurrent']} slots, ${status['cost_limit_usd']} budget")

    # Test Vibe Score
    from genesis.pipeline.reviewer import synthesize_findings, BUILTIN_ASSISTANTS
    from genesis.types import Finding
    findings = [
        Finding(title="SQL injection", severity="critical", assistantId="compliance",
                pattern="sqli", description="Raw SQL", recommendation="Use params"),
    ]
    syn = synthesize_findings(findings, BUILTIN_ASSISTANTS[:3])
    print(f"Vibe Score: {syn.vibe_score}/100 ({syn.grade})")

    # Cleanup
    os.remove("test_int.db")

    print("\n" + "=" * 55)
    print("ALL TESTS PASSING")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())

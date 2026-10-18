from fastapi.routing import APIRoute
from app.auth import require_admin


def test_every_admin_route_requires_admin(app):
    def guarded(dependency):
        return dependency.call is require_admin or any(guarded(d) for d in dependency.dependencies)
    def flatten(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, 'original_router'):
                yield from flatten(route.original_router.routes)
    routes = [r for r in flatten(app.routes) if r.path.startswith('/api/admin/')]
    assert routes
    assert all(guarded(r.dependant) for r in routes)

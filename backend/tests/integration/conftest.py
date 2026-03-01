"""
Integration-test conftest.

``app/routers/__init__.py`` eagerly imports all routers, which pulls in
heavy optional dependencies (torch, celery, tweepy, …) that are not
installed in the lean CI environment.

We short-circuit this by pre-registering ``app.routers`` as an empty
namespace package *before* any test file is collected.  When a test does
``import app.routers.cbb_sharp``, Python finds the already-registered
namespace in sys.modules and loads the sub-module directly from disk —
never executing the __init__.
"""
import sys
import types
import os

# Only inject when app.routers hasn't been imported yet.
if "app.routers" not in sys.modules:
    _pkg = types.ModuleType("app.routers")
    _pkg.__path__ = [
        os.path.join(os.path.dirname(__file__), "..", "..", "app", "routers")
    ]
    _pkg.__package__ = "app.routers"
    sys.modules["app.routers"] = _pkg

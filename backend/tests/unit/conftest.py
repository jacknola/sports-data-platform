"""
Unit-test conftest.

Some services import heavy optional packages (torch, transformers,
sentence_transformers, qdrant_client) that are not available in the lean
test environment.  We register lightweight stubs for all of them *before*
any test module is collected so that import chains succeed without needing
the real libraries.

Note: torch must expose a real `Tensor` class (not a MagicMock) because
scipy's Array API namespace dispatch uses issubclass(torch.Tensor, ...) during
import, which raises TypeError if `Tensor` is not a proper class.
"""
import sys
import types
from unittest.mock import MagicMock


def _make_torch_stub():
    """Return a minimal torch stub that won't break scipy's issubclass checks."""
    mod = types.ModuleType("torch")
    # scipy Array API dispatch checks issubclass(torch.Tensor, ...) — needs a real class
    mod.Tensor = type("Tensor", (), {})
    mod.nn = MagicMock()
    mod.optim = MagicMock()
    mod.cuda = MagicMock()
    return mod


if "torch" not in sys.modules:
    sys.modules["torch"] = _make_torch_stub()
    sys.modules["torch.nn"] = MagicMock()
    sys.modules["torch.optim"] = MagicMock()

for _mod in ["transformers", "sentence_transformers"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# qdrant_client needs a proper package hierarchy
if "qdrant_client" not in sys.modules:
    _qdrant = MagicMock()
    _qdrant_http = MagicMock()
    _qdrant_models = MagicMock()
    sys.modules["qdrant_client"] = _qdrant
    sys.modules["qdrant_client.http"] = _qdrant_http
    sys.modules["qdrant_client.http.models"] = _qdrant_models
    sys.modules["qdrant_client.models"] = _qdrant_models

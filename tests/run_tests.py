"""Minimal runner for environments without pytest:  python tests/run_tests.py
With pytest installed, prefer:  python -m pytest tests -q
"""
import contextlib, inspect, sys, traceback, types, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "pytest" not in sys.modules:
    try:
        import pytest  # noqa
    except ImportError:
        shim = types.ModuleType("pytest")
        shim.fixture = lambda f: f
        @contextlib.contextmanager
        def _raises(exc):
            try:
                yield
            except exc:
                return
            raise AssertionError(f"{exc.__name__} not raised")
        shim.raises = _raises
        sys.modules["pytest"] = shim

import test_core as T

passed = failed = 0
for name, fn in inspect.getmembers(T, inspect.isfunction):
    if not name.startswith("test_"):
        continue
    kwargs = {p: getattr(T, p)() for p in inspect.signature(fn).parameters}
    try:
        fn(**kwargs); passed += 1; print(f"PASS  {name}")
    except Exception:
        failed += 1; print(f"FAIL  {name}"); traceback.print_exc()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)

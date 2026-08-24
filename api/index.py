"""Vercel entrypoint that preserves NexiaGP's existing HTTP contract."""
from server import AppHandler


# The Python runtime discovers a *class* named ``handler``.  A subclass keeps
# every existing route and method from AppHandler while making that contract
# explicit for Vercel's function detector.
class handler(AppHandler):
    pass

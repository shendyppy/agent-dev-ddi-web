"""Eval suite for the documentation agent.

Lives at the repo root (not under ``apps/backend``) because a case is a
product-level artifact: it describes what a good answer looks like, not how
the backend is wired. ``just eval`` runs it from the root with the backend's
``src`` on ``PYTHONPATH`` so ``agent.*`` imports resolve.
"""

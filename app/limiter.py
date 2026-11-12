"""
OnCall Rehearsal Agent — Rate Limiter Instance

Centralizes slowapi Limiter instance to allow importing in route modules
without circular dependencies.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

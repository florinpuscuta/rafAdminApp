"""
Rate limiter global (slowapi). Instanță shared — importată din main.py
pentru wiring și din router-ele individuale pentru decoratori.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])

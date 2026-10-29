"""Acceso a Postgres: conexión, migraciones y estado (ADR-016).

Este paquete es el único que importa ``psycopg``, y lo hace dentro de funciones
para que la aplicación siga arrancando sin el driver cuando no hay base.
"""

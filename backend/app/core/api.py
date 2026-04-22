from fastapi import APIRouter as _APIRouter


class APIRouter(_APIRouter):
    """APIRouter cu `response_model_by_alias=True` implicit.

    Toate răspunsurile JSON ale rutelor înregistrate pe acest router sunt
    serializate folosind alias-urile (deci camelCase pentru schemele care
    extind `APISchema`). Modulele îl importă în loc de `fastapi.APIRouter`.
    """

    def add_api_route(self, path: str, endpoint, **kwargs):
        kwargs.setdefault("response_model_by_alias", True)
        return super().add_api_route(path, endpoint, **kwargs)

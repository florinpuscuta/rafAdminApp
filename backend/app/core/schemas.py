from pydantic import BaseModel, ConfigDict


def _to_camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class APISchema(BaseModel):
    """Baza pentru toate schemele expuse în API.

    Regula de naming: Python/DB folosesc snake_case, JSON-ul expus în API e camelCase.
    `populate_by_name=True` permite și clientilor care trimit snake_case să funcționeze,
    dar serializarea implicită (`model_dump(by_alias=True)`) întoarce camelCase.
    """

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

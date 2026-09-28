from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    """A request schema that refuses a field it does not define, so a typo is never ignored."""

    model_config = ConfigDict(extra='forbid')

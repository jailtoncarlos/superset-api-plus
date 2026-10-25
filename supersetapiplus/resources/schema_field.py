"""The `schema` field of the resource models that have one (datasets, saved queries)."""
import warnings

from supersetapiplus.core.api_model import ApiModel

with warnings.catch_warnings():
    # pydantic warns that the field shadows the deprecated BaseModel.schema() classmethod (replaced by
    # model_json_schema()); the field is the database schema Superset returns and accepts. Declared once here, so
    # the models inherit it without the warning (pydantic warns only where the field is annotated).
    warnings.filterwarnings("ignore", message='Field name "schema" ', category=UserWarning)

    class SchemaFieldMixin(ApiModel):
        schema: str = ''  # type: ignore[assignment]  # replaces the deprecated BaseModel.schema() (see above)

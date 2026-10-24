"""CSS templates (the CSS a dashboard editor can apply)."""
from dataclasses import dataclass, field

from supersetapiplus.core.fields import default_string
from supersetapiplus.core.model import SerializableModel
from supersetapiplus.resources.repository import ApiModelFactories


@dataclass
class CssTemplate(SerializableModel):
    """A CSS template: its name and the CSS text (applied to a dashboard through its `css` field)."""
    JSON_FIELDS = []
    PRESERVE_EXTRA_FIELDS = False
    # Fields accepted by the API (OpenAPI 6.1.0: CssTemplateRestApi.post / CssTemplateRestApi.put).
    POST_FIELDS = ("css", "template_name")
    PUT_FIELDS = ("css", "template_name")

    template_name: str
    id: int | None = field(default=None)
    css: str = default_string()


class CssTemplates(ApiModelFactories):
    """Repository of CSS templates (`client.css_templates`): CRUD and search, e.g. by `template_name`."""
    endpoint = "css_template/"

    def _default_object_class(self) -> type[SerializableModel]:
        return CssTemplate

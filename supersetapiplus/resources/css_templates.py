"""CSS templates (the CSS a dashboard editor can apply)."""

from typing import ClassVar

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.resources.repository import ApiModelFactories


class CssTemplate(ApiModel):
    """A CSS template: its name and the CSS text (applied to a dashboard through its `css` field)."""
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    # Fields accepted by the API (OpenAPI 6.1.0: CssTemplateRestApi.post / CssTemplateRestApi.put).
    POST_FIELDS: ClassVar[tuple[str, ...]] = ("css", "template_name")
    PUT_FIELDS: ClassVar[tuple[str, ...]] = ("css", "template_name")

    template_name: str
    id: int | None = None
    css: str = ''


class CssTemplates(ApiModelFactories):
    """Repository of CSS templates (`client.css_templates`): CRUD and search, e.g. by `template_name`."""
    endpoint = "css_template/"

    def _default_object_class(self) -> type[ApiModel]:
        return CssTemplate

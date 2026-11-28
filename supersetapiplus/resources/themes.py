"""Themes (Superset 6.1): an Ant Design theme configuration, applied to the whole instance or to one dashboard.

A theme is a name and ``json_data``, the JSON text of its configuration (``token``, ``components``, ``algorithm``,
...). The backend (``superset/themes/schemas.py`` and ``utils.py``, Superset 6.1.0) requires a non-empty name and a
JSON object of valid structure (``is_valid_theme``) and sanitizes the spinner and font tokens. A dashboard is bound to
a theme through its ``theme_id`` (``Dashboard.set_theme``); the dashboard page then renders inside that theme
(``CrudThemeProvider`` of ``DashboardPage.tsx``).

Two Superset tokens of the configuration change the ECharts options of the charts (``Echart.tsx``,
``utils/themeOverrides.ts`` of plugin-chart-echarts): ``echartsOptionsOverrides`` for every chart and
``echartsOptionsOverridesByChartType`` for one ``viz_type``. They are merged after the options the chart builds and
after its ``echart_options``: objects key by key, arrays replace, and an object given for ``series`` is merged into
each series of the chart (its data and formatters are kept).

The published OpenAPI specification of the 6.1.0 tag leaves the theme resource out although the server serves it;
the accepted fields come from the backend schemas (``ThemePostSchema``/``ThemePutSchema``).
"""
import json
from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import Field

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.types import ThemeAlgorithm
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError
from supersetapiplus.resources.repository import ApiModelFactories

# Keys of a theme configuration whose type the backend checks (is_valid_theme, superset/themes/utils.py).
_TYPED_KEYS: dict[str, type] = {"token": dict, "components": dict, "hashed": bool, "inherit": bool}
ECHARTS_OVERRIDES = "echartsOptionsOverrides"
ECHARTS_OVERRIDES_BY_CHART_TYPE = "echartsOptionsOverridesByChartType"


def check_theme_config(config: object) -> None:
    """The structure the backend accepts (is_valid_theme, Superset 6.1.0), so the error comes before the request.

    Raises:
        ValidationError: not an object, a typed key of another type, or an algorithm that is not a ThemeMode.
    """
    if not isinstance(config, dict):
        raise ValidationError(message="A theme configuration must be a JSON object.",
                              solution="Pass a dict such as {'token': {'colorPrimary': '#1677ff'}}.")
    wrong = [key for key, expected in _TYPED_KEYS.items() if key in config and not isinstance(config[key], expected)]
    if wrong:
        raise ValidationError(message=f"Theme configuration keys {wrong} have the wrong type; Superset expects "
                                      f"{ {key: _TYPED_KEYS[key].__name__ for key in wrong} }.",
                              solution="Fix the types; the server rejects the theme otherwise.")
    if "algorithm" in config:
        algorithm = config["algorithm"]
        allowed = {mode.value for mode in ThemeAlgorithm}
        valid = (algorithm in allowed if isinstance(algorithm, str) else
                 isinstance(algorithm, list) and all(isinstance(item, str) and item in allowed
                                                     and item != ThemeAlgorithm.SYSTEM.value for item in algorithm))
        if not valid:
            raise ValidationError(message=f"Theme algorithm {algorithm!r} is not accepted by Superset.",
                                  solution=f"Use one of {sorted(allowed)}, or a list of them without 'system'.")


def _json_object(value: Mapping[str, object], what: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(message=f"{what} must be an object (a mapping).",
                              solution="Pass a dict, e.g. {'series': {'label': {'show': True}}} for ECharts options.")
    try:
        return dict(json.loads(json.dumps(dict(value))))
    except (TypeError, ValueError) as error:
        raise ValidationError(message=f"{what} holds a value that is not JSON ({error}); a theme stores static "
                                      "values only, not functions.", solution="Replace it with a static value.") from None


class Theme(ApiModel):
    """A theme: its name and ``json_data`` (the configuration as JSON text). Read the configuration with
    :attr:`config`, replace it with :meth:`set_config`, and set the ECharts overrides with
    :meth:`set_echarts_overrides`."""
    JSON_FIELDS: ClassVar[list[str]] = []
    PRESERVE_EXTRA_FIELDS: ClassVar[bool] = False
    # Fields accepted by the API (ThemePostSchema / ThemePutSchema, superset/themes/schemas.py, Superset 6.1.0).
    POST_FIELDS: ClassVar[tuple[str, ...]] = ("json_data", "theme_name")
    PUT_FIELDS: ClassVar[tuple[str, ...]] = ("json_data", "theme_name")

    theme_name: str
    id: int | None = None
    json_data: str = "{}"
    # Read-only (set by Superset): a theme of the instance (system default or dark) cannot be edited or deleted.
    uuid: SerializableOptional[str] = None
    is_system: SerializableOptional[bool] = None
    is_system_default: SerializableOptional[bool] = None
    is_system_dark: SerializableOptional[bool] = None
    changed_on_delta_humanized: SerializableOptional[str] = Field(default=None)

    @property
    def config(self) -> dict[str, Any]:
        """The configuration stored in ``json_data`` (a new dict: change it through :meth:`set_config`)."""
        value = json.loads(self.json_data or "{}")
        return value if isinstance(value, dict) else {}

    def set_config(self, config: Mapping[str, object]) -> None:
        """Replaces the configuration, checked as the backend checks it (:func:`check_theme_config`)."""
        data = _json_object(config, "A theme configuration")
        check_theme_config(data)
        self.json_data = json.dumps(data, ensure_ascii=False)

    def set_echarts_overrides(self, all_charts: Mapping[str, object] | None = None,
                              by_chart_type: Mapping[str, Mapping[str, object]] | None = None) -> None:
        """Sets the ECharts overrides of the theme (Superset tokens ``echartsOptionsOverrides`` and
        ``echartsOptionsOverridesByChartType``), keeping the rest of the configuration.

        E.g. the value of every segment inside the bars of a stacked bar chart, with the Superset formatter kept
        (combine it with ``only_total=False`` on the chart)::

            theme.set_echarts_overrides(by_chart_type={
                "echarts_timeseries_bar": {"series": {"label": {"show": True, "position": "inside"}}}})

        Args:
            all_charts: options merged into every ECharts chart rendered with the theme; None leaves the current
                value, an empty mapping removes it.
            by_chart_type: options per ``viz_type`` (the chart's ``viz_type`` value); None leaves the current value,
                an empty mapping removes it.
        """
        config = self.config
        token = dict(config.get("token") or {})
        if all_charts is not None:
            token[ECHARTS_OVERRIDES] = _json_object(all_charts, "echartsOptionsOverrides")
            if not all_charts:
                del token[ECHARTS_OVERRIDES]
        if by_chart_type is not None:
            per_type = {str(viz_type): _json_object(options, f"echartsOptionsOverridesByChartType[{viz_type!r}]")
                        for viz_type, options in _json_object(by_chart_type, "by_chart_type").items()}
            token[ECHARTS_OVERRIDES_BY_CHART_TYPE] = per_type
            if not per_type:
                del token[ECHARTS_OVERRIDES_BY_CHART_TYPE]
        config["token"] = token
        self.set_config(config)

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset:
            return
        if not self.theme_name or not self.theme_name.strip():
            raise ValidationError(message="Theme name cannot be empty.", solution="Set theme_name.")
        try:
            config = json.loads(self.json_data)
        except (TypeError, ValueError):
            raise ValidationError(message="json_data of a theme must be the JSON text of an object.",
                                  solution="Set it with theme.set_config({...}).") from None
        check_theme_config(config)


class Themes(ApiModelFactories):
    """Repository of themes (``client.themes``): CRUD and search, e.g. by ``theme_name``. System themes (the
    instance's default and dark themes) are read-only."""
    endpoint = "theme/"

    def _default_object_class(self) -> type[ApiModel]:
        return Theme

    def delete(self, id: int) -> bool:
        """Removes a theme; True when Superset deleted it. The theme API answers ``"Deleted 1 theme"`` instead of
        the ``"OK"`` of the other resources (ThemeRestApi.delete, superset/themes/api.py, Superset 6.1.0); a theme
        that does not exist raises ``ResourceNotFoundError``, a system theme ``ForbiddenError`` and a theme in use
        as a system theme ``UnprocessableEntityError``."""
        response = self.client.delete(self.client.join_urls(self.base_url, id))
        return bool(response.ok)

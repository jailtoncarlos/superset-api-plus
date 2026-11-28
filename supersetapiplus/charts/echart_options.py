"""Custom ECharts options of a chart (the ``echart_options`` control, Superset 6.1.0, apache/superset#37868).

The control (``sharedControls.tsx``, a JSEditorControl with default ``"{}"``) is in the control panels of the
timeseries line, smooth line, bar and area charts and of the mixed timeseries chart. Its value is the text of a
JavaScript object literal, stored as a string in the params. When the chart renders, ``transformProps`` parses it
(``utils/safeEChartOptionsParser.ts``: static values only, no functions), checks it against
``customEChartOptionsSchema`` (``utils/eChartOptionsSchema.ts``) and merges it into the options the plugin built
(``utils/mergeCustomEChartOptions.ts``): objects are merged key by key, arrays and other values replace the
plugin's. A text that fails to parse or to validate is ignored as a whole, without an error in the UI.

The library writes the options as JSON (a JSON object is a JavaScript object literal). It checks what the frontend
would otherwise drop silently and what it can decide without the frontend: a JSON object whose top-level keys are
those of ``customEChartOptionsSchema``. The nested values are checked by the frontend only.
"""
import json
import math
from collections.abc import Mapping
from typing import Protocol

from supersetapiplus.core.api_model import ApiModel
from supersetapiplus.core.typing import SerializableOptional
from supersetapiplus.exceptions import ValidationError

# Top-level keys of customEChartOptionsSchema (eChartOptionsSchema.ts, Superset 6.1.0); the parser drops any other
# key (validatePartial). tests/unit/test_enum_conformance.py checks them against the excerpt of the source.
ECHART_OPTION_KEYS: frozenset[str] = frozenset({
    "backgroundColor", "darkMode", "textStyle", "useUTC",
    "animation", "animationThreshold", "animationDuration", "animationEasing", "animationDelay",
    "animationDurationUpdate", "animationEasingUpdate", "animationDelayUpdate", "stateAnimation",
    "title", "legend", "grid", "xAxis", "yAxis", "tooltip", "toolbox", "dataZoom", "visualMap", "axisPointer",
    "graphic", "series",
})

EMPTY_ECHART_OPTIONS = "{}"  # the control default


def _check_values(value: object, path: str) -> None:
    """Static JSON values only: what the frontend parser accepts and the library can write as JSON."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(message=f"echart_options key {key!r} at {path or 'the top level'} is not a "
                                              "string.", solution="Use string keys, as in an ECharts option object.")
            _check_values(item, f"{path}.{key}" if path else key)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_values(item, f"{path}[{index}]")
    elif isinstance(value, float) and math.isnan(value):
        return  # written as NaN, which the parser reads as NaN
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise ValidationError(
            message=f"echart_options value at {path} is a {type(value).__name__}; Superset accepts static values "
                    "only (objects, arrays, strings, numbers, booleans, null), not functions.",
            solution="Replace it with a static value; formatter functions cannot be set through echart_options.")


def echart_options_text(options: Mapping[str, object]) -> str:
    """The ``echart_options`` text for `options` (an ECharts option object), checked as described in the module.

    Raises:
        ValidationError: `options` has a top-level key the frontend drops, or a value that is not static.
    """
    if not isinstance(options, Mapping):
        raise ValidationError(message="echart_options must be an object (a mapping of ECharts option keys).",
                              solution="Pass a dict such as {'legend': {'show': False}}.")
    unknown = sorted(str(key) for key in options if key not in ECHART_OPTION_KEYS)
    if unknown:
        raise ValidationError(
            message=f"echart_options keys {unknown} are not accepted by Superset 6.1.0 (customEChartOptionsSchema); "
                    "the frontend drops them.",
            solution=f"Use the keys {sorted(ECHART_OPTION_KEYS)}.")
    _check_values(options, "")
    return json.dumps(dict(options), ensure_ascii=False)


class EChartOptionsMixin(ApiModel):
    """The ``echart_options`` param of the charts whose control panel has the control."""
    echart_options: SerializableOptional[str] = EMPTY_ECHART_OPTIONS

    def validate(self) -> None:  # type: ignore[override]  # facade method, not pydantic's deprecated classmethod
        super().validate()
        if self._read_from_superset or self.echart_options in (None, ""):
            return  # what Superset stored (possibly a JavaScript literal written in Explore) is sent as read
        try:
            options = json.loads(self.echart_options)
        except (TypeError, ValueError):
            raise ValidationError(
                message="echart_options of a chart built in code must be the JSON text of an object.",
                solution="Set it with chart.set_echart_options({...}).") from None
        echart_options_text(options)


class _EChartOptionsChart(Protocol):
    @property
    def params(self) -> EChartOptionsMixin: ...

    @property
    def query_context(self) -> object: ...


class EChartOptionsChartMixin:
    """``set_echart_options`` of the charts with the ``echart_options`` control: the params and the stored
    query_context form_data get the same text."""

    def set_echart_options(self: _EChartOptionsChart, options: Mapping[str, object] | None) -> None:
        """Overrides the ECharts options the chart plugin builds, e.g. ``{"legend": {"show": False}}``.

        Superset merges objects key by key and replaces arrays and other values: a ``series`` given here replaces
        the series the plugin built (with their data) instead of merging into them, and the same holds for any
        array (``xAxis: [...]``, ``dataZoom: [...]``). Function values (formatters) are not accepted by Superset.

        Args:
            options: the ECharts option object; None or an empty mapping clears the override (``"{}"``).

        Raises:
            ValidationError: a top-level key Superset does not accept, or a value that is not static.
        """
        text = EMPTY_ECHART_OPTIONS if not options else echart_options_text(options)
        self.params.echart_options = text
        form_data = getattr(self.query_context, "form_data", None)
        if isinstance(form_data, EChartOptionsMixin):
            form_data.echart_options = text

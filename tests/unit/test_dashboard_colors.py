"""Categorical color schemes of the frontend and the dashboard's color_scheme_domain: pure logic, no HTTP.

The 6.1.0 dashboard frontend (src/dashboard/actions/dashboardState.ts) asks to store the domain whenever the stored
``color_scheme_domain`` is not, color by color, the colors of ``color_scheme`` in its categorical registry; the
extraction script (bin/scripts/extract_color_schemes.py) is checked here on synthetic sources, without network.
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from supersetapiplus.dashboards import colors
from supersetapiplus.dashboards.metadata import Metadata

SCRIPT = Path(__file__).parents[2] / "bin" / "scripts" / "extract_color_schemes.py"
spec = importlib.util.spec_from_file_location("extract_color_schemes", SCRIPT)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

SETUP_TS = """
  registerColorSchemes(
    getCategoricalSchemeRegistry(),
    [
      ...CategoricalFirst,
      ...CategoricalSecond,
      ...extraCategoricalColorSchemes,
    ],
    'secondColors',
  );
  registerColorSchemes(getSequentialSchemeRegistry(), [...SequentialCommon], 'superset_seq_1');
"""
INDEX_TS = """
export { default as CategoricalFirst } from './first';
export { default as CategoricalSecond } from './second';
"""
FIRST_TS = """
const schemes = [
  {
    id: 'firstColors',
    label: 'First Colors',
    colors: [
      '#111111',
      '#222222',
    ],
  },
  {
    id: 'otherColors',
    label: 'Other Colors',
    group: ColorSchemeGroup.Featured,
    colors: [
      // Full color
      '#aaaaaa',
      // Pastels
      '#BBBBBB',
    ],
  },
].map(s => new CategoricalScheme(s));
"""
SECOND_TS = FIRST_TS.replace("firstColors", "secondColors").replace("otherColors", "thirdColors")
SOURCES = {extractor.SETUP_PATH: SETUP_TS, f"{extractor.CATEGORICAL_DIR}/index.ts": INDEX_TS,
           f"{extractor.CATEGORICAL_DIR}/first.ts": FIRST_TS, f"{extractor.CATEGORICAL_DIR}/second.ts": SECOND_TS}


def fetch(sources):
    return lambda version, path: sources[path]


def test_the_registered_schemes_are_extracted_in_order_with_the_default():
    result = extractor.extract("9.9.9", fetch(SOURCES))
    assert list(result["schemes"]) == ["firstColors", "otherColors", "secondColors", "thirdColors"]
    assert result["schemes"]["otherColors"] == {"label": "Other Colors", "colors": ["#aaaaaa", "#BBBBBB"]}
    assert result["default"] == "secondColors"
    assert result["provenance"]["paths"][-1] == f"{extractor.CATEGORICAL_DIR}/second.ts"


def test_a_scheme_marked_default_wins_over_the_default_key():
    sources = dict(SOURCES)
    sources[f"{extractor.CATEGORICAL_DIR}/first.ts"] = FIRST_TS.replace(
        "label: 'First Colors',", "label: 'First Colors',\n    isDefault: true,")
    assert extractor.extract("9.9.9", fetch(sources))["default"] == "firstColors"


@pytest.mark.parametrize(("path", "source", "message"), [
    (extractor.SETUP_PATH, "setupColors();\n", "categorical registration"),
    (f"{extractor.CATEGORICAL_DIR}/index.ts", "export * from './first';\n", "no export"),
    (f"{extractor.CATEGORICAL_DIR}/first.ts", re.sub(r"'(#\w+)'", r'"\1"', FIRST_TS), "no color"),
    (f"{extractor.CATEGORICAL_DIR}/second.ts", "const schemes = [];\n", "no scheme"),
])
def test_a_source_whose_format_changed_fails_instead_of_giving_an_empty_set(path, source, message):
    with pytest.raises(SystemExit, match=message):
        extractor.extract("9.9.9", fetch({**SOURCES, path: source}))


def test_the_shipped_schemes_record_their_provenance_and_default():
    shipped = json.loads((Path(colors.__file__).parent / "profiles" / "color_schemes_6.1.0.json").read_text())
    assert shipped["provenance"]["tag"] == "6.1.0" and len(shipped["provenance"]["sha"]) == 40
    assert colors.default_categorical_scheme() == "supersetColors"
    assert colors.categorical_scheme("supersetColors").colors[:3] == ("#1FA8C9", "#454E7C", "#5AC189")
    assert len(colors.categorical_scheme("d3Category10").colors) == 10


def test_an_unknown_scheme_or_version_is_refused():
    with pytest.raises(ValueError, match="unknown categorical color scheme 'noSuchColors'.*EXTRA_CATEGORICAL"):
        colors.categorical_scheme("noSuchColors")
    with pytest.raises(ValueError, match="no categorical color schemes for Superset 0.0.0"):
        colors.categorical_schemes("0.0.0")


def test_setting_the_scheme_fills_the_domain_with_its_colors_in_order():
    metadata = Metadata()
    metadata.set_color_scheme("d3Category10")
    assert metadata.color_scheme == "d3Category10"
    assert metadata.color_scheme_domain == list(colors.categorical_scheme("d3Category10").colors)
    assert metadata.to_dict()["color_scheme_domain"] == metadata.color_scheme_domain


def test_changing_the_scheme_of_a_read_dashboard_rewrites_the_domain():
    metadata = Metadata.from_json({"color_scheme": "d3Category10", "color_scheme_domain": ["#1f77b4"]})
    metadata.set_color_scheme("lyftColors")
    assert metadata.color_scheme_domain == list(colors.categorical_scheme("lyftColors").colors)


def test_an_instance_scheme_takes_its_colors_and_no_scheme_clears_the_domain():
    metadata = Metadata()
    metadata.set_color_scheme("instanceColors", colors=["#123456", "#654321"])
    assert (metadata.color_scheme, metadata.color_scheme_domain) == ("instanceColors", ["#123456", "#654321"])
    metadata.set_color_scheme("")
    assert (metadata.color_scheme, metadata.color_scheme_domain) == ("", [])
    with pytest.raises(ValueError, match="unknown categorical color scheme"):
        metadata.set_color_scheme("instanceColors")

"""Example charts whose copy returns other data than Explore shows for the original, each with its GitHub issues.

Found when the reference became the query Explore sends (``example_query_contexts_6.1.0.json``): before building the
query, Explore normalizes the stored params, and the library builds from them as stored. Keyed by the chart UUID of
the examples (stable across stacks). The data check reports these charts as KnownDivergenceWarning instead of failing,
and fails when one of them returns the data of the original: remove it from here when its issues are fixed.

- #23: legacy ``since``/``until`` not turned into ``time_range``;
- #24: absent or null control values not replaced by the control defaults;
- #25: stored keys that are not controls of the viz_type sent in the query;
- #26: legacy ``granularity_sqla`` not migrated to ``x_axis``.
"""
KNOWN_DATA_DIVERGENCES: dict[str, tuple[int, ...]] = {
    "2a5e562b-ab37-1b9b-1de3-1be4335c8e83": (24, 25),  # Games (table)
    "d8bf948e-46fd-4380-9f9c-a950c34bcc92": (24, 26),  # Total Sales per Market (Grouped by Genre) (echarts_timeseries_bar)
    "1810975a-f6d4-07c3-495c-c3b535d01f21": (24,),  # Most Dominant Platforms (pie)
    "d20b7324-3b80-24d4-37e2-3bd583b66713": (25,),  # Publishers With Most Titles (table)
    "a40879d5-653a-42fe-9314-bbe88ad26e92": (26,),  # Top 10 Games: Proportion of Sales in Markets (echarts_timeseries_bar)
    "db9609e4-9b78-4a32-87a7-4d9e19d51cd8": (24, 26),  # Quarterly Sales (By Product Line) (echarts_timeseries_bar)
    "09c497e0-f442-1121-c9e7-671e37750424": (24,),  # Overall Sales (By Product Line) (pie)
    "f065a533-2e13-42b9-bd19-801a21700dff": (24, 26),  # Revenue by Deal Size (echarts_timeseries_bar)
    "a6dd2d5a-2cdc-c8ec-f30c-85920f4f8a65": (24,),  # ✈️ Relocation ability (pie)
    "edc75073-8f33-4123-a28d-cd6dfb33cade": (24,),  # First Time Developer? (pie)
    "6d0ceb30-2008-d19c-d285-cf77dc764433": (24,),  # How much do you expect to earn? ($0 - 100k) (histogram_v2)
    "0f6b447c-828c-e71c-87ac-211bc412b214": (24,),  # Gender (pie)
    "def07750-b5c0-0b69-6228-cb2330916166": (24,),  # Are you an ethnic minority in your city? (pie)
    "e6b09c28-98cf-785f-4caf-320fd4fca802": (24,),  # Work Location Preference (pie)
    "9f742bdd-cac1-468c-3a37-35c9b3cfd5bb": (26,),  # Weekly Threads (big_number)
    "abe2c022-ceee-a60a-e601-ab93f7ee52b1": (26,),  # Weekly Messages (big_number)
    "92e1d712-bcf9-4d7e-9b94-26cffe502908": (26,),  # New Members per Month (big_number)
    "b0f11bdf-793f-473f-b7d5-b9265e657896": (24, 26),  # Messages per Channel (echarts_area)
    "e7f37c36-35b4-45f5-a323-9c1d1ff69d04": (24, 26),  # Trends (echarts_timeseries_line)
    "2a58a195-f5eb-4a08-a061-cbe49168eb24": (24,),  # Boys (table)
    "b092147d-6068-41b5-a4a4-acc789ce5ebe": (26,),  # Genders by State (echarts_timeseries_bar)
    "13be7d94-ead6-465e-97ef-a5d419621c29": (24,),  # Girls (table)
    "44c4c16f-216d-44c8-b033-6876b8c51fd2": (24, 26),  # Top 10 Girl Name Share (echarts_area)
    "a20d8fff-79b1-4419-83bf-3080f93d6908": (26,),  # Participants (big_number)
    "26a9bde8-eb06-4de3-91f0-5e04d448403a": (24, 26),  # Top 10 Boy Name Share (echarts_area)
    "53c450c6-98bf-435a-8ebb-2a237bccfd09": (23, 24),  # Box plot (box_plot)
    "c18faec9-ec43-4d36-8b66-4c8b1372020f": (23,),  # Life Expectancy VS Rural % (bubble_v2)
    "cdac97d6-28a2-4cff-a1d0-c8b81dcf29a6": (23,),  # Rural Breakdown (sunburst_v2)
    "6f7e8cc4-c850-4992-85a4-b161a782abc6": (23, 24, 26),  # World's Pop Growth (echarts_area)
    "78422cf9-f149-4491-b552-2ab0e3afffcf": (23, 26),  # World's Population (big_number)
    "71a12856-38a5-4978-be65-d0f4fde98aae": (23,),  # Treemap (treemap_v2)
    "6cf742ee-281a-4673-a37c-587d6f29726a": (23, 24, 26),  # Growth Rate (echarts_timeseries_line)
}

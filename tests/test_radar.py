from app.collect.base import Candidate
from app.digest import radar

NOW = "2026-08-11T12:00:00Z"


def _c(cid, views=1000, posted_at="2026-08-11T00:00:00Z"):
    return Candidate(
        id=f"youtube:{cid}",
        platform="youtube",
        native_id=cid,
        url=f"https://www.youtube.com/watch?v={cid}",
        creator=None,
        caption=None,
        posted_at=posted_at,
        views=views,
        likes=None,
        comments=None,
        source="trending",
    )


def _classify_by_prefix(candidate):
    """Fake rubric call: ids starting with 'emo' are Erez's genre."""
    return {"fits_erez_style": candidate.native_id.startswith("emo")}


def test_sort_region_routes_by_fits_erez_style():
    chart = [_c("emo1"), _c("gen1"), _c("emo2")]

    emotional, general = radar.sort_region(
        chart, classify=_classify_by_prefix, quotas=radar.Quotas()
    )

    assert [c.native_id for c, _ in emotional] == ["emo1", "emo2"]
    assert [c.native_id for c in general] == ["gen1"]


def test_sort_region_keeps_the_analysis_it_paid_for():
    emotional, _ = radar.sort_region(
        [_c("emo1")],
        classify=lambda c: {"fits_erez_style": True, "hook": "h"},
        quotas=radar.Quotas(),
    )

    assert emotional[0][1]["hook"] == "h"


def test_sort_region_stops_probing_at_the_budget():
    calls = []

    def classify(candidate):
        calls.append(candidate.native_id)
        return {"fits_erez_style": False}

    radar.sort_region(
        [_c(f"v{i}") for i in range(10)], classify=classify, quotas=radar.Quotas(probes=4)
    )

    assert len(calls) == 4  # every probe is a paid Gemini call — the cap is the cost dial


def test_sort_region_stops_early_when_both_quadrants_are_full():
    calls = []

    def classify(candidate):
        calls.append(candidate.native_id)
        return {"fits_erez_style": candidate.native_id.startswith("emo")}

    chart = [_c("emo1"), _c("gen1"), _c("emo2"), _c("gen2"), _c("never-probed")]
    emotional, general = radar.sort_region(
        chart, classify=classify, quotas=radar.Quotas(emotional=2, general=2, probes=10)
    )

    assert len(emotional) == 2 and len(general) == 2
    assert "never-probed" not in calls


def test_sort_region_skips_a_video_that_could_not_be_analyzed():
    emotional, general = radar.sort_region(
        [_c("broken"), _c("emo1")],
        classify=lambda c: None if c.native_id == "broken" else {"fits_erez_style": True},
        quotas=radar.Quotas(),
    )

    assert [c.native_id for c, _ in emotional] == ["emo1"]
    assert general == []


def test_quotas_default_to_erezs_spec_when_settings_lack_them():
    quotas = radar.quotas_from({"digest": {}})

    assert (quotas.emotional, quotas.general) == (3, 2)  # 3+3+2+2 = 10, fixed 2026-07-25


def test_quotas_read_erezs_overrides():
    quotas = radar.quotas_from(
        {
            "digest": {
                "radar": {
                    "emotional_per_region": 1,
                    "general_per_region": 1,
                    "probe_per_region": 2,
                }
            }
        }
    )

    assert (quotas.emotional, quotas.general, quotas.probes) == (1, 1, 2)


def test_pick_keeps_israel_and_world_as_separate_sections():
    charts = {
        "israel": [_c("emo-il"), _c("gen-il")],
        "world": [_c("emo-w"), _c("gen-w")],
    }

    deep, light = radar.pick(
        charts, [], classify=_classify_by_prefix, quotas=radar.Quotas(), now=NOW
    )

    assert [(c.native_id, s) for c, s in deep] == [("emo-il", "israel"), ("emo-w", "world")]
    assert [(c.native_id, s) for c, s in light] == [("gen-il", "israel"), ("gen-w", "world")]


def test_pick_lets_the_pool_compete_for_world_slots_by_velocity():
    # A fast-climbing topic-search find must be able to beat a chart video.
    charts = {"world": [_c("emo-slow", views=100, posted_at="2026-08-09T12:00:00Z")]}
    pool = [_c("emo-pool", views=2_000_000, posted_at="2026-08-11T10:00:00Z")]

    deep, _ = radar.pick(
        charts, pool, classify=_classify_by_prefix, quotas=radar.Quotas(emotional=1), now=NOW
    )

    assert [(c.native_id, s) for c, s in deep] == [("emo-pool", "world")]


def test_pick_shows_a_video_trending_in_both_regions_once():
    hit = _c("emo-hit")
    charts = {"israel": [hit], "world": [hit]}

    deep, light = radar.pick(
        charts, [], classify=_classify_by_prefix, quotas=radar.Quotas(), now=NOW
    )

    assert [(c.native_id, s) for c, s in deep] == [("emo-hit", "israel")]
    assert light == []


def test_collect_charts_survives_a_dead_chart():
    class _Boom:
        def chart(self):
            raise RuntimeError("quota")

    class _Ok:
        def chart(self):
            return [_c("emo1")]

    charts = radar.collect_charts({"israel": _Boom(), "world": _Ok()}, excluded=lambda c: False)

    assert charts["israel"] == []  # a dead chart loses its section, not the morning
    assert [c.native_id for c in charts["world"]] == ["emo1"]


def test_collect_charts_applies_erezs_excluded_formats():
    class _Src:
        def chart(self):
            return [_c("emo1"), _c("redcarpet1")]

    charts = radar.collect_charts(
        {"world": _Src()}, excluded=lambda c: "redcarpet" in c.native_id
    )

    assert [c.native_id for c in charts["world"]] == ["emo1"]

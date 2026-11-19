"""Do not mistake PDF/H.264 raster bias for an out-of-window highlight.

Calibrate only against strong decoded-frame on/off evidence. Persistent,
faint or unverified overlays must continue to fail closed.
"""
import pytest
from microgen_measured_highlight_video_qa import _off_control_verified


@pytest.mark.parametrize("active,inactive,temporal", [
    (55.683, 9.025, 52.497),
    (55.411, 9.348, 52.405),
    (45, 8.2, 30),
    (60, 12, 50),
])
def test_independent_decoded_transition_confirms_highlight(active,inactive,temporal):
    assert _off_control_verified(active=active,inactive=inactive,
                                 temporal_change=temporal)


@pytest.mark.parametrize("active,inactive,temporal", [
    (55,55,0),   # persistent highlight never switched off
    (55,40,15),  # substantial persistent off-window highlight
    (55,20,30),  # off-state too strong relative to active
    (55,12,10),  # no independently visible decoded-frame transition
    (28,9,25),   # source-frame PDF bias not sufficient separation
    (55,float("nan"),55),
    (float("inf"),9,52),
    (55,-1,52),
])
def test_real_temporal_leak_or_unverifiable_measurement_still_blocks(
        active,inactive,temporal):
    assert not _off_control_verified(active=active,inactive=inactive,
                                     temporal_change=temporal)


def test_falsified_positives_do_not_change_the_threshold():
    assert not _off_control_verified(active=55,inactive=17,temporal_change=35)
    assert _off_control_verified(active=55,inactive=8.4,temporal_change=0)


from microgen_measured_highlight_video_qa import (
    _source_roi_overlap_fraction, MAX_OFF_CONTROL_SOURCE_ROI_OVERLAP_FRACTION,
)


def test_same_source_region_is_never_independent_off_control():
    a=(10,10,50,30)
    assert _source_roi_overlap_fraction(a,a)==1
    assert _source_roi_overlap_fraction(a,(60,10,70,20))==0
    assert _source_roi_overlap_fraction(a,(48,10,52,30))==0.05
    assert 0.05 > MAX_OFF_CONTROL_SOURCE_ROI_OVERLAP_FRACTION
    assert _source_roi_overlap_fraction(a,(49,10,50,30)) == 0.025


def test_very_small_boundary_touch_is_not_a_shared_active_region():
    a=(10,10,50,30)
    assert _source_roi_overlap_fraction(a,(50,10,70,30))==0


from microgen_measured_highlight_video_qa import _timed_source_region_visible


def test_large_actual_text_regions_have_area_aware_visibility():
    assert _timed_source_region_visible(54.21,9.71,(123,271,546,352),
                                        independently_controlled=True)
    assert _timed_source_region_visible(55.69,9.33,(108,200,541,271),
                                        independently_controlled=True)
    assert not _timed_source_region_visible(54.21,9.71,(123,271,546,352),
                                            independently_controlled=False)


def test_large_roi_fallback_rejects_missing_or_global_change():
    large=(123,271,546,352)
    for active,whole in ((40,30),(18,8),(float('nan'),9), (54,90)):
        assert not _timed_source_region_visible(active,whole,large,
                                                independently_controlled=True)
    assert not _timed_source_region_visible(54.21,9.71,(0,0,40,20),
                                            independently_controlled=True)

import unittest

from trend_fvg.confluence import fvgs_overlapping_fib, intersect_zone
from trend_fvg.models import FVG


def _fvg(gap_low, gap_high, kind="bullish"):
    return FVG(idx1=0, idx2=1, idx3=2, kind=kind, gap_low=gap_low, gap_high=gap_high, confirmed_idx=6)


class TestFvgsOverlappingFib(unittest.TestCase):
    def test_matches_when_a_level_is_inside_the_fvg(self):
        fvg = _fvg(20, 30)
        matches = fvgs_overlapping_fib([fvg], {0.618: 25})
        self.assertEqual(matches, [(fvg, 0.618)])

    def test_no_match_when_no_level_is_inside(self):
        fvg = _fvg(20, 30)
        matches = fvgs_overlapping_fib([fvg], {0.618: 50})
        self.assertEqual(matches, [])


class TestIntersectZone(unittest.TestCase):
    def test_fvg_narrower_than_fib_band(self):
        # FVG fully inside the fib band [16.82, 24.044] -- intersection
        # is the FVG itself.
        fvg = _fvg(18, 22)
        fib_levels = {0.382: 24.044, 0.295: 20.39, 0.21: 16.82}
        self.assertEqual(intersect_zone(fvg, fib_levels), (18, 22))

    def test_fib_band_narrower_than_fvg(self):
        # This is the reported bug scenario: FVG [20, 30] is much wider
        # than the fib band [16.82, 24.044] -- the intersection must be
        # clipped down to the fib band's portion, not the full FVG.
        fvg = _fvg(20, 30)
        fib_levels = {0.382: 24.044, 0.295: 20.39, 0.21: 16.82}
        self.assertEqual(intersect_zone(fvg, fib_levels), (20, 24.044))

    def test_partial_overlap_low_side(self):
        fvg = _fvg(10, 22)
        fib_levels = {0.618: 20, 0.5: 25, 0.382: 30}  # fib band [20, 30]
        self.assertEqual(intersect_zone(fvg, fib_levels), (20, 22))

    def test_partial_overlap_high_side(self):
        fvg = _fvg(25, 40)
        fib_levels = {0.618: 20, 0.5: 25, 0.382: 30}  # fib band [20, 30]
        self.assertEqual(intersect_zone(fvg, fib_levels), (25, 30))

    def test_no_overlap_returns_none(self):
        fvg = _fvg(0, 10)
        fib_levels = {0.618: 20, 0.5: 25, 0.382: 30}  # fib band [20, 30]
        self.assertIsNone(intersect_zone(fvg, fib_levels))

    def test_downtrend_style_levels_unordered_in_dict_still_work(self):
        # fib_levels for a downtrend can have the numerically lower ratio
        # mapped to the higher price -- intersect_zone must use min/max of
        # the values, not assume any particular ratio->price ordering.
        fvg = _fvg(70, 85)
        fib_levels = {0.21: 89.5, 0.295: 85.25, 0.382: 80.9}  # band [80.9, 89.5]
        self.assertEqual(intersect_zone(fvg, fib_levels), (80.9, 85))


if __name__ == "__main__":
    unittest.main()

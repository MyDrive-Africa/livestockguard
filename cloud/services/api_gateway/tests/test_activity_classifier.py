"""Tests for activity classification algorithm."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.activity_classifier import (
    classify_activity,
    haversine_distance,
    ActivityResult,
)


class TestClassifyActivity:
    """Activity classifier logic."""

    def test_resting_low_speed(self):
        result = classify_activity(
            speeds=[0.1, 0.0, 0.2, 0.05],
            headings=[90, 91, 89, 90],
            distances_m=[1, 0, 2, 0.5],
        )
        assert result.activity == 'resting'
        assert result.confidence > 0.5

    def test_walking_moderate_speed(self):
        result = classify_activity(
            speeds=[4.0, 5.0, 4.5, 3.8, 5.2],
            headings=[180, 182, 181, 183, 182],
            distances_m=[50, 60, 55, 48, 62],
        )
        assert result.activity == 'walking'

    def test_running_high_speed(self):
        result = classify_activity(
            speeds=[12.0, 14.0, 11.5, 13.0],
            headings=[45, 46, 44, 45],
            distances_m=[200, 220, 190, 210],
        )
        assert result.activity == 'running'
        assert result.avg_speed > 8.0

    def test_grazing_slow_with_high_heading_variance(self):
        # Zig-zag pattern: lots of direction changes
        result = classify_activity(
            speeds=[1.0, 0.8, 1.2, 0.9, 1.1, 0.7, 1.0, 0.8],
            headings=[10, 80, 150, 30, 200, 90, 310, 50],  # Large changes
            distances_m=[10, 8, 12, 9, 11, 7, 10, 8],
        )
        assert result.activity == 'grazing'
        assert result.heading_variance > 0

    def test_empty_data_returns_resting(self):
        result = classify_activity(speeds=[], headings=[], distances_m=[])
        assert result.activity == 'resting'
        assert result.confidence == 0.5

    def test_single_point_returns_classification(self):
        result = classify_activity(
            speeds=[3.0],
            headings=[90],
            distances_m=[],
        )
        # Single point at 3 km/h — walking
        assert result.activity == 'walking'

    def test_confidence_bounded(self):
        result = classify_activity(
            speeds=[50.0, 60.0],  # Extreme speed
            headings=[0, 0],
            distances_m=[1000, 1200],
        )
        assert 0.0 <= result.confidence <= 1.0


class TestHaversineDistance:
    """GPS distance calculation."""

    def test_zero_distance(self):
        d = haversine_distance(-29.12, 26.21, -29.12, 26.21)
        assert d == 0.0

    def test_known_distance_approx(self):
        # ~111 km per degree of latitude
        d = haversine_distance(0.0, 0.0, 1.0, 0.0)
        assert 110_000 < d < 112_000

    def test_short_distance(self):
        # Two points ~100m apart
        d = haversine_distance(-29.1200, 26.2100, -29.1209, 26.2100)
        assert 90 < d < 110

    def test_symmetry(self):
        d1 = haversine_distance(-29.12, 26.21, -29.13, 26.22)
        d2 = haversine_distance(-29.13, 26.22, -29.12, 26.21)
        assert abs(d1 - d2) < 0.01

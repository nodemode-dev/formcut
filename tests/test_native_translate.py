"""The compositing kernel's integer-translation path, to the bit.

A layer moved by whole pixels, the identity included, is fetched directly rather
than sampled; OpenCV's warp gives the same numbers there, and these hold the
kernel to it in every direction, across the edges, at several opacities, and one
hair away from an integer, where the general path takes over.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_native import BUILT, CANVAS, kernel, pictures, python_path

SHIFTS = [(0, 0), (7, 3), (-5, 11), (13, -2), (-40, -25), (CANVAS[1] - 3, CANVAS[0] - 2), (-CANVAS[1] + 4, 1), (500, 500)]


@BUILT
@pytest.mark.parametrize("tx, ty", SHIFTS)
@pytest.mark.parametrize("alpha", [1.0, 0.37, 0.0])
@pytest.mark.parametrize("source", [(30, 50), (CANVAS[0] + 20, CANVAS[1] + 30)])
def test_a_layer_moved_by_whole_pixels_is_bit_identical(tx, ty, alpha, source):
    image, canvas = pictures(source, seed=abs(tx * 31 + ty) + source[0])
    matrix = np.array([[1.0, 0.0, float(tx)], [0.0, 1.0, float(ty)]])
    assert np.array_equal(kernel(canvas, image, matrix, alpha), python_path(canvas, image, matrix, alpha))


@BUILT
@pytest.mark.parametrize("fraction", [1e-9, 0.5, 0.999])
def test_a_shift_off_the_integers_takes_the_sampled_path_and_matches(fraction):
    image, canvas = pictures((30, 50), seed=3)
    matrix = np.array([[1.0, 0.0, 12 + fraction], [0.0, 1.0, 7 - fraction]])
    assert np.array_equal(kernel(canvas, image, matrix, 0.8), python_path(canvas, image, matrix, 0.8))

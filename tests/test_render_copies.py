"""mask_frame copies only when a key, a mask or a cutout will change the picture."""

import numpy as np
from app.renderer import FrameRenderer
from conftest import make_project, text_clip


def test_a_frame_without_key_mask_or_cutout_passes_through_and_a_keyed_one_is_copied():
    renderer = FrameRenderer(make_project(clips=[text_clip()]))
    try:
        image = np.full((12, 16, 4), 200, np.uint8)
        image[:, :, 1] = 255
        assert renderer.mask_frame(image, {"id": "a"}) is image
        before = image.copy()
        keyed = renderer.mask_frame(image, {"id": "a", "key": {"color": "#c8ffc8", "similarity": 0.3, "blend": 0.05}})
        assert keyed is not image and np.array_equal(image, before)
        assert int(keyed[:, :, 3].max()) < 255
    finally:
        renderer.close()

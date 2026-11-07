# Credits for the deliver demo media

Every file below was opened on its source page and its licence read there before it was downloaded. None of it is formcut's own work, and none of it is covered by formcut's Apache-2.0 licence; each keeps the licence on its source page. The demo ships them as JavaScript data packs in `assets/media/` (`talk-01.js` to `talk-08.js`, `voice.js`, `music.js`) with `film.js` as the manifest; each pack holds the re-encoded file as base64 so the page can decode it from `file://`. Nothing from `examples/demo` is used.

The Pexels License (https://www.pexels.com/license/) allows free use and modification, asks for no attribution, and forbids selling unaltered copies, redistributing the files on other stock platforms, implying endorsement, and portraying identifiable people badly. The picture shows landscapes, sky, water and fire; no person, logo or brand is a subject of any clip.

## Video, from Pexels

Eight clips, video track kept and audio dropped, a span cut from each, scaled to 1280x720 with Lanczos, re-encoded H.264 (x264, CRF 27, `-preset veryfast`, keyframe every 15 frames, faststart) at 30 fps. Some of the Pexels clips are the same as in the other two demos, cut at other spans and colour-graded only by the page at play time.

| Demo name | File in the demo | Title | Photographer | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| First light (`talk-01`) | `talk-01.js` | Stunning Mountain Sunrise Aerial View | GIANG VU | https://www.pexels.com/video/stunning-mountain-sunrise-aerial-view-33354461/ | License: Free (Pexels License) | 2560x1440 source, 11.5 s from 0:18 |
| Mist and pine (`talk-02`) | `talk-02.js` | Aerial View of Misty Forest in Autumn | Julien Goettelmann | https://www.pexels.com/video/aerial-view-of-misty-forest-in-autumn-29792712/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps, 11.5 s from 0:02.5, 30 fps |
| The stream (`talk-03`) | `talk-03.js` | Stunning Cascading Waterfall in Remote Valley | Gylfi Gylfason | https://www.pexels.com/video/stunning-cascading-waterfall-in-remote-valley-40393750/ | License: Free (Pexels License) | 2560x1440 source, 11.5 s from 0:10 |
| Open water (`talk-04`) | `talk-04.js` | Silhouette Of Mountains At Sunset | Engin Akyurt | https://www.pexels.com/video/silhouette-of-mountains-at-sunset-1722697/ | License: Free (Pexels License) | 3840x2160 source at 25 fps, 11.5 s from 0:30, 30 fps |
| Peaks (`talk-05`) | `talk-05.js` | Dramatic Sunrise Over Snowy Swiss Peaks | Marek Piwnicki | https://www.pexels.com/video/dramatic-sunrise-over-snowy-swiss-peaks-39264188/ | License: Free (Pexels License) | 2560x1440 source, 11.5 s from 0:08 |
| Fire (`talk-06`) | `talk-06.js` | Evening Campfire Glowing in Dark Outdoors | yaman ozuduru | https://www.pexels.com/video/evening-campfire-glowing-in-dark-outdoors-33667473/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps, 11.5 s from 0:14, 30 fps |
| Above the clouds (`talk-07`) | `talk-07.js` | Breathtaking Sunrise Over Ocean of Clouds | 小小 兵 (pexels.com/@1516822895) | https://www.pexels.com/video/breathtaking-sunrise-over-ocean-of-clouds-34470558/ | License: Free (Pexels License) | 2560x1440 source, 11.5 s from 0:40 |
| Night sky (`talk-08`) | `talk-08.js` | Stunning Milky Way Timelapse Over Mountains | Erhan Dayi (@moments) | https://www.pexels.com/video/stunning-milky-way-timelapse-over-mountains-39220755/ | License: Free (Pexels License) | 2560x1440 source at 24 fps, first 12.5 s, 30 fps |

## Voice

| Demo name | File in the demo | Title | Reader and project | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Walden, Where I Lived (`talk-voice`) | `voice.js` | Henry David Thoreau, Walden (1854), chapter 2 "Where I Lived, and What I Lived For", part 2 (`walden_c02_p02_64kb.mp3`) | Gord Mackenzie for LibriVox | https://archive.org/details/walden_librivox | Usage: Public Domain, license URL http://creativecommons.org/licenses/publicdomain/ | 78 s cut from 0:28.6 (the opening "I went to the woods"), 70 Hz high-pass, loudness normalised (EBU R128, -18 LUFS integrated, -1.5 dBTP), mono, MP3 80 kbps |

The captions in `src/data.ts` are Thoreau's public-domain text, hand-typed and timed against a word-level alignment of the recording made with an offline speech model (Vosk small English, Apache-2.0) used only as a build tool; the model is not shipped.

## Music

| Demo name | File in the demo | Title | Performer and project | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Goldberg Variation 13 (`talk-music`) | `music.js` | J.S. Bach, Variatio 13 a 2 Clav., BWV 988 (The Open Goldberg Variations) | Kimiko Ishizaka | https://archive.org/details/OpenGoldbergVariations | CC0 1.0 Universal, license URL http://creativecommons.org/publicdomain/zero/1.0/ | Ogg Vorbis file from the item, first 90 s, loudness normalised (EBU R128, -21 LUFS integrated, -1.5 dBTP), 44.1 kHz stereo, MP3 112 kbps |

## Reframe paths

`src/paths.ts` holds crop paths produced by running the engine's own `reframe()` (`backend/app/subject.py`) on the shipped clips at 2 frames per second; they are numbers derived from the footage and carry no licence of their own.

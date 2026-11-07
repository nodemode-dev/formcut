# Credits for the demo media

Every file below was opened on its source page and its licence read there before it was downloaded. None of it is formcut's own work, and none of it is covered by formcut's Apache-2.0 licence; each keeps the licence on its source page. The demo ships them as JavaScript data packs in `demo/assets/media/` (`clip-NN.js`, `music.js`) with `film.js` as the manifest; the packs hold the re-encoded files as base64 so the page can decode them from `file://`.

The Pexels License (https://www.pexels.com/license/) allows free use and modification, asks for no attribution, and forbids selling unaltered copies, redistributing the files on other stock platforms, implying endorsement, and portraying identifiable people badly. The film shows landscapes, sky, fire and water; no person, logo or brand is a subject of any clip.

## Video, from Pexels

All eight clips: video track kept, audio dropped, trimmed to the span used, cropped to 16:9 where needed, scaled to 1280x720 with Lanczos, re-encoded H.264 (x264, CRF 21, `-preset veryfast`, keyframe every 15 frames, faststart). The 60 fps sources were reduced to 30 fps.

| Demo name | File in the demo | Title | Photographer | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Milky Way (`film-01`) | `clip-01.js` | Stunning Milky Way Timelapse Over Mountains | Erhan Dayi (@moments) | https://www.pexels.com/video/stunning-milky-way-timelapse-over-mountains-39220755/ | License: Free (Pexels License) | 2560x1440 source file; first 7.0 s; 1280x720; 24 fps |
| Sunrise ridge (`film-02`) | `clip-02.js` | Stunning Mountain Sunrise Aerial View | GIANG VU | https://www.pexels.com/video/stunning-mountain-sunrise-aerial-view-33354461/ | License: Free (Pexels License) | 2560x1440 source; 7.9 s from 0:03; 1280x720; 30 fps |
| Snow peaks (`film-03`) | `clip-03.js` | Dramatic Sunrise Over Snowy Swiss Peaks | Marek Piwnicki | https://www.pexels.com/video/dramatic-sunrise-over-snowy-swiss-peaks-39264188/ | License: Free (Pexels License) | 2560x1440 source; 6.4 s from 0:02; 1280x720; 30 fps |
| Fog and forest (`film-04`) | `clip-04.js` | Aerial View of Misty Forest in Autumn | Julien Goettelmann | https://www.pexels.com/video/aerial-view-of-misty-forest-in-autumn-29792712/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps; 6.9 s from 0:01; 1280x720; 30 fps |
| Waterfall slope (`film-05`) | `clip-05.js` | Stunning Cascading Waterfall in Remote Valley | Gylfi Gylfason | https://www.pexels.com/video/stunning-cascading-waterfall-in-remote-valley-40393750/ | License: Free (Pexels License) | 2560x1440 source; 6.9 s from 0:04; 1280x720; 30 fps |
| Cloud sea (`film-06`) | `clip-06.js` | Breathtaking Sunrise Over Ocean of Clouds | 小小 兵 (pexels.com/@1516822895) | https://www.pexels.com/video/breathtaking-sunrise-over-ocean-of-clouds-34470558/ | License: Free (Pexels License) | 2560x1440 source; 8.4 s from 0:28; 1280x720; 30 fps |
| Campfire (`film-07`) | `clip-07.js` | Evening Campfire Glowing in Dark Outdoors | yaman ozuduru | https://www.pexels.com/video/evening-campfire-glowing-in-dark-outdoors-33667473/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps; 6.9 s from 0:05; 1280x720; 30 fps |
| Southern lights (`film-08`) | `clip-08.js` | Stunning Southern Lights Over Queenstown Lake | Eclipse Chasers | https://www.pexels.com/video/stunning-southern-lights-over-queenstown-lake-34794659/ | License: Free (Pexels License) | 2158x1440 source; cropped to 2158x1214 (16:9); 8.9 s from 0:02; 1280x720; 25 fps |

## Music

| Demo name | File in the demo | Title | Performer and project | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Goldberg Aria (`film-music`) | `music.js` | J.S. Bach, Aria from the Goldberg Variations, BWV 988 (track 01 of The Open Goldberg Variations) | Kimiko Ishizaka | https://archive.org/details/OpenGoldbergVariations | CC0 1.0 Universal, license URL http://creativecommons.org/publicdomain/zero/1.0/ | Ogg Vorbis file from the item; first 1.7 s of lead-in silence removed, 52 s kept, loudness normalised (EBU R128, -17 LUFS integrated, -1.5 dBTP), resampled to 44.1 kHz, MP3 128 kbps |

## Not used

freepd.com was considered and not used: its home page says the site is permanently closed and its category pages no longer answer. The Musopen recording of Grieg's Morning Mood on Wikimedia Commons (public domain on its description page) was read and chosen first, but upload.wikimedia.org refused every download with HTTP 429, so it was dropped rather than fetched by other means. `examples/demo` carries no licence grant and nothing from it is in this demo.

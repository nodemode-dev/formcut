# Credits for the grade demo media

Every file below was opened on its source page and its licence read there before it was downloaded. None of it is formcut's own work, and none of it is covered by formcut's Apache-2.0 licence; each keeps the licence on its source page. The demo ships them as JavaScript data packs in `assets/media/` (`grade-01.js` to `grade-06.js`, `music.js`) with `film.js` as the manifest; each pack holds the re-encoded file as base64 so the page can decode it from `file://`. Nothing from `examples/demo` is used.

The Pexels License (https://www.pexels.com/license/) allows free use and modification, asks for no attribution, and forbids selling unaltered copies, redistributing the files on other stock platforms, implying endorsement, and portraying identifiable people badly. The film shows landscapes, sky, water and fire; no person, logo or brand is a subject of any clip.

## Video, from Pexels

Six clips, video track kept and audio dropped, a span cut from each, scaled to 1280x720 with Lanczos, re-encoded H.264 (x264, CRF 25, `-preset veryfast`, keyframe every 15 frames, faststart) at 30 fps. Each is deliberately flattened on encode (`eq=contrast=0.80:saturation=0.74:brightness=0.025`) so the grade the page applies has room to work; this is a change to the file and is shown as such in the Media tab.

| Demo name | File in the demo | Title | Photographer | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Last light (`grade-01`) | `grade-01.js` | Silhouette Of Mountains At Sunset | Engin Akyurt | https://www.pexels.com/video/silhouette-of-mountains-at-sunset-1722697/ | License: Free (Pexels License) | 3840x2160 source at 25 fps, 13 s from 0:03, flattened, 30 fps |
| Open water (`grade-02`) | `grade-02.js` | Silhouette Of Mountains At Sunset | Engin Akyurt | https://www.pexels.com/video/silhouette-of-mountains-at-sunset-1722697/ | License: Free (Pexels License) | the same file, 10 s from 0:34, flattened, 30 fps |
| Warm peaks (`grade-03`) | `grade-03.js` | Dramatic Sunrise Over Snowy Swiss Peaks | Marek Piwnicki | https://www.pexels.com/video/dramatic-sunrise-over-snowy-swiss-peaks-39264188/ | License: Free (Pexels License) | 2560x1440 source, 10 s from 0:04, flattened |
| Mist and pine (`grade-04`) | `grade-04.js` | Aerial View of Misty Forest in Autumn | Julien Goettelmann | https://www.pexels.com/video/aerial-view-of-misty-forest-in-autumn-29792712/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps, 10 s from 0:02, flattened, 30 fps |
| Fire (`grade-05`) | `grade-05.js` | Evening Campfire Glowing in Dark Outdoors | yaman ozuduru | https://www.pexels.com/video/evening-campfire-glowing-in-dark-outdoors-33667473/ | License: Free (Pexels License) | 1920x1080 source at 59.94 fps, 8.5 s from 0:12, flattened, 30 fps |
| Southern lights (`grade-06`) | `grade-06.js` | Stunning Southern Lights Over Queenstown Lake | Eclipse Chasers | https://www.pexels.com/video/stunning-southern-lights-over-queenstown-lake-34794659/ | License: Free (Pexels License) | 2158x1440 source at 25 fps, cropped to 2158x1214 (16:9), 11 s from 0:08, flattened |

## Music

| Demo name | File in the demo | Title | Performer and project | Source page | Licence as stated on the page | What changed |
| --- | --- | --- | --- | --- | --- | --- |
| Goldberg Variation 13 (`grade-music`) | `music.js` | J.S. Bach, Variatio 13 a 2 Clav., BWV 988 (The Open Goldberg Variations) | Kimiko Ishizaka | https://archive.org/details/OpenGoldbergVariations | CC0 1.0 Universal, license URL http://creativecommons.org/publicdomain/zero/1.0/ | Ogg Vorbis file from the item, first 46 s, loudness normalised (EBU R128, -17 LUFS integrated, -1.5 dBTP), 4 s fade out, 44.1 kHz stereo, MP3 128 kbps |

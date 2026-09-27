# Community caption looks

Caption looks made by people who use formcut, shipped with it and listed in the Captions panel after formcut's own
looks, each with its author's name.

## Add yours

1. In formcut, style a caption track the way you want it: pick a look, change the word style and its colour.
2. In the Captions panel, give the look a name and your GitHub handle, and choose **Share this look**. formcut saves
   `<id>.json`, a captions package: anyone can install it as it is (Effects, Packages, Install), and it is the file
   this folder takes.
3. Open a pull request that adds it here as `backend/app/community_looks/<id>/manifest.json`, the file unchanged,
   and a line in the pull request saying you made the look and are contributing it under the Apache License 2.0.

A look is only a style: the keys formcut's own looks use, and a word style of none, highlight, pop, box, reveal or
rise. The tests load every folder here exactly as the package installer loads a package, draw its card, and fail on
a look that does not load, whose id another look uses, or that has no author. Looks follow the
[code of conduct](../../../CODE_OF_CONDUCT.md): a name or style that breaks it is not accepted.

## The manifest

```json
{
  "id": "night-bus-by-yourhandle",
  "name": "Night bus",
  "kind": "captions",
  "author": "yourhandle",
  "style": {
    "size": 6,
    "color": "#ffffff",
    "bold": true,
    "weight": 800,
    "align": "center",
    "outlineColor": "#000000",
    "outlineWidth": 4,
    "wordStyle": { "mode": "rise", "colour": "#7cf0ff" }
  }
}
```

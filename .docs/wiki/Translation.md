# Translation

formcut ships in 12 languages: English, Spanish, German, French, Italian,
Japanese, Korean, Brazilian Portuguese, Russian, Turkish, Simplified Chinese and
Traditional Chinese. The language is chosen on the home screen or in Settings;
switching reloads the app, because panes render their chrome once.

## Where strings live

- `frontend/src/i18n/en.json`, `es.json` and `de.json` hold keyed strings, read
  with `t(key)`.
- `frontend/src/i18n/language-pack.ts` holds the other nine languages as rows:
  the English phrase, then French, Italian, Japanese, Korean, Brazilian
  Portuguese, Russian, Turkish, Simplified Chinese and Traditional Chinese,
  separated by `|`. A key resolves in these languages through its English
  value. Every row must have exactly ten fields, or the app stops at start-up.
- `frontend/src/i18n/text.ts` translates English phrases already written into
  the interface: `text(phrase)` for one string, `localizeElement(root)` for the
  text, `title`, `placeholder` and `aria-label` of a whole subtree. German and
  Spanish phrases that have no key live in its `additional` maps.

## The rule

An English phrase is translated only if it has a translation and it passes
through `t()`, `text()` or `localizeElement()` at the moment it reaches the
screen. `main.ts` localizes the whole page once every pane and menu is built.
Anything written after that, such as names that arrive from the engine, rows
that load asynchronously, or labels that change with state, must call `text()`
where it is written.

- Never read a translated label back to learn state. Keep the value in a data
  attribute or in an option's `value`, and display it through `text()`. The
  blend mode control keeps its mode in `data-mode` for this reason.
- A select shows labels, never ids: set `value` to the id and the text to a
  readable English label. Code reads the select only through `.value`.
- Phrase matching is exact and global. Before adding a single-word phrase,
  check that every place the word appears in the interface means the same thing.
- When two rows share an English source, the later one wins. Do not add a row
  for a phrase that already has one.

## Checking coverage

Run the app in Japanese and look for Latin-script text. Anything left is either
untranslated or deliberately left as it is: language names in their own
language, user content such as track and timeline names, file types, and code
such as the expression example. The scan used for each release visits every
tab, menu, creator page and select option, including pages that stay hidden
until chosen.

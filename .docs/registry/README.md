# formcut's community registry

`effects-registry.json` lists packages anyone can install from formcut's effects browser (**Community packages**):
effect stacks, audio chains and caption looks. Each entry names a zip of a package folder and its SHA-256; formcut
downloads it, checks the hash, and installs it through the same checks as a package dropped into the browser. formcut
reads this index from its raw GitHub URL; `FORMCUT_PACKAGE_REGISTRY` points it at another.

## List a caption look

1. In formcut, style a caption track: pick a look, set the word style (highlight, pop, box, reveal or rise) and its
   colour.
2. In the Captions panel, give the look a name and your GitHub handle and choose **Share this look**. formcut saves
   `<id>.zip`, made the way the packages here are (stored, one fixed date, the manifest's keys sorted), so the same
   look always makes the same file.
3. From a clone of formcut:

   ```
   python setup/registry_entry.py ~/Downloads/<id>.zip --description "What it looks like, in a sentence." --add
   ```

   The tool checks the zip as formcut's installer does, refuses an id the registry already lists, copies the zip to
   `packages/` and appends its entry with the hash.
4. Open a pull request with the zip and the entry, saying you made the look and contribute it under the Apache
   License 2.0.

Any package works the same way: a zip of its folder (`manifest.json`, plus its `shader.wgsl` or audio template), then
the tool. The tests install every package listed here and fail on a hash that does not match or a package formcut
would refuse. Names and looks follow the [code of conduct](../../CODE_OF_CONDUCT.md).

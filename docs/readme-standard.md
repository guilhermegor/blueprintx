# README standard for repositories BlueprintX did not scaffold

BlueprintX scaffolds get the README gate for free (see [README Layout Gate](readme-layout.md)).
A repository created some other way adopts the same gate by vendoring two files and wiring one
hook and one CI step. The layout rules themselves live in `readme-layout.md`; this page is only
the adoption procedure.

## The layout in one screen

- First line: `<!-- readme-archetype: NAME -->`, then the H1.
- The logo is centered on its own line under the H1, at width 200, from an absolute
  `raw.githubusercontent.com` URL (a relative path breaks on PyPI).
- The canonical badge row follows, then the slug-marked sections in the order the archetype
  defines, a `documentation` section where the archetype requires one, and a footer: a rule and
  a `<sub>` line, with no heading.
- No heading carries an emoji or an image.

The archetypes are `library`, `cli`, `spa`, `service`, `usb-tool` and `toolkit`. Pick
`toolkit` for a machine-setup or configuration repository driven by Make or task targets and
without releases: it requires a `commands` section in place of `public-api` and `publishing`.

## 1. Vendor the two files

Copy these from BlueprintX into the target repository, keeping the relative layout:

| Source in BlueprintX | Destination |
|---|---|
| `templates/common/bin/check_readme_structure.sh` | `bin/check_readme_structure.sh` |
| `templates/common/bin/lib/md_structure.sh` | `bin/lib/md_structure.sh` |

The gate sources its parser from `lib/md_structure.sh` next to itself, so the two stay together.

## 2. Add the pre-commit hook

```yaml
      - id: readme-structure
        name: README structure
        entry: bash bin/check_readme_structure.sh README.md
        language: system
        pass_filenames: false
        files: ^(README\.md|bin/check_readme_structure\.sh|bin/lib/md_structure\.sh)$
```

## 3. Add the CI step

```yaml
      - name: README structure
        run: bash bin/check_readme_structure.sh README.md
```

## 4. Re-sync when the gate changes

The vendored copies drift silently, so compare them with BlueprintX on every upgrade:

```bash
for f in bin/check_readme_structure.sh bin/lib/md_structure.sh; do
  curl -fsSL "https://raw.githubusercontent.com/guilhermegor/BlueprintX/main/templates/common/$f" \
    | diff -u "$f" - && echo "in sync: $f"
done
```

Replace a file whose diff is non-empty, then run the gate. Never edit a vendored copy in place:
fix the gate in BlueprintX and re-sync.

## Worked example: filings-rfb

`guilhermegor/filings-rfb#33` is the reference adoption. Its README opens with the archetype
marker, the centered logo and the canonical badge row, carries a `documentation` section that
points to the docs site and the local serve command, ends with the `<sub>` footer, and passes
`bash bin/check_readme_structure.sh README.md` in both pre-commit and CI.

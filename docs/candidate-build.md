# Keep a candidate build

The **Retain candidate as draft** workflow builds the generic image and example
companion on a public standard GitHub runner. It keeps the result in an
unpublished release draft, rather than discarding the firmware when the runner
stops. It does not publish a release or deploy anything to a NAS.

After the workflow is merged into `main`, open its page under Actions and choose
**Run workflow**, with `main` selected. Other branches and forks are rejected by
the job condition. There are no private configuration inputs.

The job checks release access before compiling and creates a uniquely named
draft. If the build fails, that draft may be empty or incomplete. Do not publish
it. A completed run uploads these seven assets:

- `uImage.buffalo`: generic kernel and RAM root filesystem;
- `initrd.buffalo`: anonymous example companion;
- `sources.tar`: exact source inputs, recipes, patches and resolved configurations;
- `THIRD-PARTY-NOTICES.tar`: original license and copyright notices;
- `build.manifest` and `packages.manifest`;
- `SHA256SUMS`: checksums of all six other assets.

Sources and notices finish uploading before the firmware upload starts. The job
checks that the release is still a draft before and after these uploads. It
never overwrites an existing asset or changes the draft to a public release.

Draft releases are available to repository users with push access. See
[GitHub's release API documentation](https://docs.github.com/en/rest/releases/releases).
Download the assets while signed into that account and verify `SHA256SUMS`.
Keep the sources and notices with their matching firmware.

The workflow must run from `main`: GitHub's built-in Actions token cannot create
a release for a commit whose workflow files differ from the default branch.
Only this manually started, main-branch job receives repository write permission;
the ordinary pull-request CI remains read-only.

Keeping a draft is not hardware acceptance or public distribution approval.
The [public distribution requirements](distribution.md) still apply before
publishing it. A successful build also does not establish bit-for-bit
reproducibility; that comparison is a separate test.

For an existing local build and its collected sources, prepare the same assets
without uploading anything:

```sh
python3 scripts/package-release-candidate.py \
  --artifacts build/artifacts \
  --sources build/source-review \
  --output build/release
```

The output directory must not exist. The packager verifies the source and
firmware inventories, requires the notice archive, and writes `SHA256SUMS`
only after checking the completed copies.

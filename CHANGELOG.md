# CHANGELOG



## v0.5.3 (2023-11-30)

### Fix

* fix: Pin TDS version back to 7.0

pymssql with TDS 7.3 parses datetime2 as datetime, leading
to a drop in timestamp resolution (100 ns -&gt; ~3 ms). This causes
incorrect frames to occasionally be grabbed from Beholder. ([`dd64838`](https://github.com/mbari-org/vars-gridview/commit/dd64838db9944a69ce2ccc3265c0997acead2d32))


## v0.5.2 (2023-11-29)

### Chore

* chore: Update CI workflow to include poetry publishing

Remove pyinstaller build/release for now ([`777066d`](https://github.com/mbari-org/vars-gridview/commit/777066d042a026e732aa8a7299766b48310128c9))

### Fix

* fix: Pin TDS version to 7.3 ([`12af446`](https://github.com/mbari-org/vars-gridview/commit/12af44648a3f2653deec53aa973ebb5f8a7663da))


## v0.5.1 (2023-11-28)

### Fix

* fix: Sharktopoda resize calculation ([`f5a7716`](https://github.com/mbari-org/vars-gridview/commit/f5a771666f5e56e83a1a5860ac4da4a554fb140d))

### Unknown

* Merge branch &#39;develop&#39; ([`dea745a`](https://github.com/mbari-org/vars-gridview/commit/dea745abcb63e1c9f9b2db8d0f5524ebf8b69dfa))

* Add zip step for macOS app upload ([`5bfecac`](https://github.com/mbari-org/vars-gridview/commit/5bfecac4bc24348367def11d37a4f9913e2e9c01))

* Remove version environment variable from CI ([`ce5970c`](https://github.com/mbari-org/vars-gridview/commit/ce5970c6c5dc42620327e6fa3084ac5c462919cd))

* Stringify Python version in CI ([`b9785b7`](https://github.com/mbari-org/vars-gridview/commit/b9785b798f8c8e036a3ea1c68caf5a92653f637f))

* Add python-semantic-release package ([`230be93`](https://github.com/mbari-org/vars-gridview/commit/230be9361206469cc8ef9e6dd58f13e07344dcda))

* Merge branch &#39;feat/semantic-release&#39; into develop ([`7acd838`](https://github.com/mbari-org/vars-gridview/commit/7acd8389ab2f237c555b20b72b8630f5e0e3a0b1))

* Merge branch &#39;feat/package&#39; into develop ([`33fd581`](https://github.com/mbari-org/vars-gridview/commit/33fd581050d69c280c831d7d3495bf5af5dcab1f))

* Add macOS app artifact upload and download ([`58010d5`](https://github.com/mbari-org/vars-gridview/commit/58010d5f857beb5035a87381bf1c72394095e640))

* Checkpoint ([`198e17f`](https://github.com/mbari-org/vars-gridview/commit/198e17f8d94210c93c057363219ae3c3bbf36611))

* Add semantic-release configuration ([`e7b8818`](https://github.com/mbari-org/vars-gridview/commit/e7b88182694a756f452a014d08d1ce79fc1efdb6))

* Update sharktopoda-client version ([`3c78c0b`](https://github.com/mbari-org/vars-gridview/commit/3c78c0bd9e35c8010039bc3890557476c7394219))

* Add isort, flake8, and pre-commit config

The commit adds the following files:

- `.isort.cfg`: Configuration file for isort with the &#34;black&#34; profile.
- `.flake8`: Configuration file for flake8 with max line length set to
88 and extended ignore rules.
- `.pre-commit-config.yaml`: Configuration file for pre-commit with
hooks for isort, black, and flake8. ([`cf7486b`](https://github.com/mbari-org/vars-gridview/commit/cf7486bfa953f7a40313d6a224c1997218091b88))


## v0.5.0 (2023-11-28)

### Unknown

* Bump version ([`ad76bb0`](https://github.com/mbari-org/vars-gridview/commit/ad76bb0dd5e75baa71ed09ed3bd12c11afb62a52))

* Merge branch &#39;kevinsbarnard/issue39&#39; into develop ([`09c7cce`](https://github.com/mbari-org/vars-gridview/commit/09c7cce94d14fb0c8eaa640f05376da9fcc256ef))

* Add warning for different MP4 aspect ratio ([`b6fc31e`](https://github.com/mbari-org/vars-gridview/commit/b6fc31eb08b11270c3b2e59f498b03d8294cbda2))

* Remove varsObservationsLabel from infoPanel ([`f16ee82`](https://github.com/mbari-org/vars-gridview/commit/f16ee8244c07a554c626c4eed11c13110455c82e))

* Add observation observer to image info list ([`b33d4c3`](https://github.com/mbari-org/vars-gridview/commit/b33d4c3f3015b9cd22fbffe4c4289302f9d89078))


## v0.4.8 (2023-11-28)

### Unknown

* Add keyboard nav to grid view
Implements #58 ([`6b5e7e9`](https://github.com/mbari-org/vars-gridview/commit/6b5e7e915b67f175c6807f1d597df5682967ff67))

* Merge branch &#39;develop&#39; into feat/package ([`fe54646`](https://github.com/mbari-org/vars-gridview/commit/fe54646ac6a45f72c0a742ef376191ba972f893e))

* Add user log directory path ([`2f6252c`](https://github.com/mbari-org/vars-gridview/commit/2f6252c3e7f784f1c32fc78a5f30efbf330d6eb4))

* Add app icon ([`6ab860f`](https://github.com/mbari-org/vars-gridview/commit/6ab860fa56e2c0cf0945bce68d7d3d3f4080d6de))

* Set field/size policies ([`8b16e12`](https://github.com/mbari-org/vars-gridview/commit/8b16e122d5ce100667700471b8ba770450f87360))

* Add mac app bundle ([`14e8191`](https://github.com/mbari-org/vars-gridview/commit/14e8191e4cdcea7e95d5616c30870f597b2a7d52))

* Update size policies for line edits ([`a37d8d3`](https://github.com/mbari-org/vars-gridview/commit/a37d8d3c2a4a15c6bf4929969f195f1d42de05f4))

* Update Python version and add pyinstaller ([`b0703a3`](https://github.com/mbari-org/vars-gridview/commit/b0703a30bd5b3b51c870866f8224f442e8932a16))

* Setup for pyinstaller build ([`4217862`](https://github.com/mbari-org/vars-gridview/commit/4217862520c507219af19d587887924bc3feff36))


## v0.4.7 (2023-11-22)

### Unknown

* Bump version ([`c515b67`](https://github.com/mbari-org/vars-gridview/commit/c515b67c5130ac150637b9d8ecbaf158112799f2))

* Force TDS version 7.0 ([`d34e288`](https://github.com/mbari-org/vars-gridview/commit/d34e288ae2b2ebf2a08b97bd9263710f6a05f300))

* Various improvements to error handling ([`eadec72`](https://github.com/mbari-org/vars-gridview/commit/eadec72245769a87682e4ad0549a66f1d98210e4))

* Rescale localizations for Sharktopoda 2 ([`66a4abc`](https://github.com/mbari-org/vars-gridview/commit/66a4abcd5e53da95f2315f230bf9769fb82e9bf3))


## v0.4.6 (2023-11-21)

### Unknown

* Bump version ([`e7f07a3`](https://github.com/mbari-org/vars-gridview/commit/e7f07a3ece71f79feaf88b0f124e73cde5bae608))

* Add setting for selection highlight color ([`4e77a08`](https://github.com/mbari-org/vars-gridview/commit/4e77a082c41ca66cc3c540a6c6451aed505f139e))


## v0.4.5 (2023-11-17)

### Unknown

* Bump version ([`03342c0`](https://github.com/mbari-org/vars-gridview/commit/03342c0707eda992a86039420f8fec9f3bb5f40f))

* Add toolbar object name ([`9aac4e2`](https://github.com/mbari-org/vars-gridview/commit/9aac4e2a984c695dcd359760290ea193ed3e3bcc))

* Skip imaged moments without video start timestamp
or sequence name

Fixes #56 ([`f203824`](https://github.com/mbari-org/vars-gridview/commit/f203824c2cf93dce4b98b30d5676e3bd4e6adf0e))


## v0.4.4 (2023-11-17)

### Unknown

* Fix handling of empty concept/part in ImageMosaic
class ([`74c91eb`](https://github.com/mbari-org/vars-gridview/commit/74c91eb10439e41f9b864de19017713a8b225b57))


## v0.4.3 (2023-11-15)

### Unknown

* GUI improvements

- Add Font Aweseome icons for settings/query
- Add toolbar (on left) with relevant actions
- Save/restore style in GUI settings ([`2129a13`](https://github.com/mbari-org/vars-gridview/commit/2129a1352d56b3c00ff3981366ef9e466267be0f))


## v0.4.2 (2023-11-14)

### Unknown

* Bump version ([`91eb7bf`](https://github.com/mbari-org/vars-gridview/commit/91eb7bf39f9cba90bce654f333bf2ddb69b97384))

* Merge branches &#39;kevinsbarnard/issue40&#39; and &#39;kevinsbarnard/issue43&#39; into develop ([`bd59ed4`](https://github.com/mbari-org/vars-gridview/commit/bd59ed4238424f459262598526d62810197150ff))

* Autorange only on image change
Fixes #40 ([`ff06c8f`](https://github.com/mbari-org/vars-gridview/commit/ff06c8fa18dfbb987e5f4da8a7ede37f8670f792))

* Apply a chronological sort by default
Fixes #43 ([`1b6ec10`](https://github.com/mbari-org/vars-gridview/commit/1b6ec1053a819ed36e35811b46712aa7ab578788))


## v0.4.1 (2023-11-14)

### Unknown

* Add warning dialog for when no results are loaded
in sorting, labeling, and deleting functions. Fixes #38 ([`18575cd`](https://github.com/mbari-org/vars-gridview/commit/18575cd98af846fa9d7c66c4380d9c5f4c975be3))


## v0.4.0 (2023-11-14)

### Unknown

* Bump version ([`28415c1`](https://github.com/mbari-org/vars-gridview/commit/28415c12d0fe3dbfe47643217201a42dfb9782be))

* Merge branch &#39;feature/sharktopoda2&#39; into develop ([`e41312a`](https://github.com/mbari-org/vars-gridview/commit/e41312a596b3a6a59f6523166771a99cf198fd45))


## v0.3.17 (2023-11-14)

### Unknown

* Bump version to 0.3.17 ([`7d7a3c7`](https://github.com/mbari-org/vars-gridview/commit/7d7a3c70aa65d0a7acaa628e64bace9ab3be8a2c))

* Merge branch &#39;develop&#39; of github.com:mbari-org/vars-gridview into develop ([`af2b76f`](https://github.com/mbari-org/vars-gridview/commit/af2b76fefbea10bd7a3fd37abb493bc4ba17cc7f))

* Map concept name to official KB name and add
get_concept method to VARSKBServerClient ([`65c3557`](https://github.com/mbari-org/vars-gridview/commit/65c35573ee1ea6874a19f8807ed720713dca8ce7))

* Connection working with shark-client 0.4.4 ([`7337e3c`](https://github.com/mbari-org/vars-gridview/commit/7337e3c4109f1e6a754fa2d490f2c451a7aeea70))

* Merge branch &#39;develop&#39; into feature/sharktopoda2 ([`9be650a`](https://github.com/mbari-org/vars-gridview/commit/9be650a53aee4478db955e699e82649270171e7c))


## v0.3.16 (2023-11-08)

### Unknown

* Revert conditional lookup of video info ([`a86dc93`](https://github.com/mbari-org/vars-gridview/commit/a86dc9327b624c35bee088128cb01dd724b874b9))


## v0.3.15 (2023-11-08)

### Unknown

* Bump version ([`2324fb8`](https://github.com/mbari-org/vars-gridview/commit/2324fb8ce013039eabeeecccb415ed9919c41872))

* Fix several issues with query result untangling ([`8f8422e`](https://github.com/mbari-org/vars-gridview/commit/8f8422e06db192ce7447a20f08bd83d768096a6f))

* Add get_image_reference method to AnnosaurusClient ([`54cbcf2`](https://github.com/mbari-org/vars-gridview/commit/54cbcf2ac2735e80d16b6406e5b350f7e1ea207a))

* Add function to get image reference by UUID ([`288523f`](https://github.com/mbari-org/vars-gridview/commit/288523f4dd7e00a5d034fa9f49e5016813bd42b8))

* Avoid bug in pymssql value formatting ([`16ea7b4`](https://github.com/mbari-org/vars-gridview/commit/16ea7b42bbd7cec7a9b798d18e1f730b2d22d708))


## v0.3.14 (2023-10-05)

### Unknown

* Update video data store with datetime objects ([`4665040`](https://github.com/mbari-org/vars-gridview/commit/466504053f0c568dbd329ee313f06c0eeb7bc36c))


## v0.3.13 (2023-10-05)

### Unknown

* Patch fix for Apple Silicon issue ([`1e9cfd7`](https://github.com/mbari-org/vars-gridview/commit/1e9cfd7f83e1d27e82e169602a7450a48f8c7150))


## v0.3.12 (2023-10-05)

### Unknown

* Relax constraint on pymssql ([`6a9f86a`](https://github.com/mbari-org/vars-gridview/commit/6a9f86a9d00f404173c4d6db3ccfd0e1aaba801f))


## v0.3.11 (2023-10-05)

### Unknown

* Bump version ([`227f995`](https://github.com/mbari-org/vars-gridview/commit/227f995d780dd813c8e38e29f0654a8963b099da))

* Handle unparsed datetime fields

Note: This handles a bug (likely in FreeTDS) on Apple Silicon where
datetimes SQL columns are not parsed according to ISO-8601, and instead
return the string representation.

Fixes #32 ([`5edac61`](https://github.com/mbari-org/vars-gridview/commit/5edac6106847d990044bc98d1193ff5a43ddd578))


## v0.3.10 (2023-09-27)

### Unknown

* Bump version ([`298723d`](https://github.com/mbari-org/vars-gridview/commit/298723d89dd69a62dd6f1f1634a166f765d00663))

* Merge pull request #35 from mbari-org/33-handle-resolution-difference-between-annotation-source-video-mp4-proxy

Add resolution scaling ([`8e026ba`](https://github.com/mbari-org/vars-gridview/commit/8e026ba7e07ac8313e46ba785c79edb4d2332868))


## v0.3.9 (2023-09-26)

### Unknown

* Bump version ([`0d1cc61`](https://github.com/mbari-org/vars-gridview/commit/0d1cc61bd1ecbdd6abb7427f12f339602d2efbb6))

* Merge pull request #34 from mbari-org/30-full-frame-view

Autorange on rect click, closes #30 ([`1620d85`](https://github.com/mbari-org/vars-gridview/commit/1620d856e5e69edc7f406efac24534948a92034a))

* Autorange on rect click, closes #30 ([`a8c9ddb`](https://github.com/mbari-org/vars-gridview/commit/a8c9ddb50ae782e55290faeed7a4cb7ce79f8893))


## v0.3.8 (2023-09-26)

### Unknown

* Upgrade deps, add sleep to S2 show ([`0d423d1`](https://github.com/mbari-org/vars-gridview/commit/0d423d19164abd0d3ba7e0fece74cb4fb9fa217b))

* Add resolution scaling ([`2f0e2b1`](https://github.com/mbari-org/vars-gridview/commit/2f0e2b1724ea41b0f70ead90f1f2d0079c72c561))

* Typo ([`20f3de6`](https://github.com/mbari-org/vars-gridview/commit/20f3de67f908473dcef17f56196f31f45c2afa3a))

* Log invalid/oob boxes ([`ef39569`](https://github.com/mbari-org/vars-gridview/commit/ef395694be58d4a5fe1e3cb92e5e92bc743123e6))

* Rework logging a bit ([`436b07e`](https://github.com/mbari-org/vars-gridview/commit/436b07ea30b3d20adcb94c91a5cf60a822cbdfc1))

* Video player check point ([`f9a4c4f`](https://github.com/mbari-org/vars-gridview/commit/f9a4c4fc7b796e049c8b7f58fadcb29c6901a767))

* Background sharktopoda connect, opencv-python dep ([`08b580b`](https://github.com/mbari-org/vars-gridview/commit/08b580bd29750ddf4326dffe717b64adabe5b479))


## v0.3.7 (2023-08-23)

### Unknown

* Bump version ([`7c28ad7`](https://github.com/mbari-org/vars-gridview/commit/7c28ad71e85257ae685ca0162b624cc238ad319e))

* Left click select/right click menu in image ([`924041b`](https://github.com/mbari-org/vars-gridview/commit/924041b35d471c585dff698d1167a54e3960468c))


## v0.3.6 (2023-08-23)

### Unknown

* Bump version ([`5b6efeb`](https://github.com/mbari-org/vars-gridview/commit/5b6efeb658b15c030c9278da643f98feefcbbd4f))

* Add setting for font size ([`6010d95`](https://github.com/mbari-org/vars-gridview/commit/6010d953e2336270a533d9f9c9c00fee61f0af36))


## v0.3.5 (2023-08-22)

### Unknown

* Bump version ([`17f13ba`](https://github.com/mbari-org/vars-gridview/commit/17f13bae8220faafb22dbd708046d6c93547774a))

* Remove re-sort on layout update ([`df75ebc`](https://github.com/mbari-org/vars-gridview/commit/df75ebc90d2bb70f2226734654fbb0d42bcd2aa9))

* Keep settings tabs updated from external changes ([`94d48ac`](https://github.com/mbari-org/vars-gridview/commit/94d48acda107c4393e27b1e6a0f232c11fbcada7))


## v0.3.4 (2023-08-19)

### Unknown

* Bump version ([`7fcd673`](https://github.com/mbari-org/vars-gridview/commit/7fcd673b49858a7ec9c3a71028861273dd8e1cf8))

* Merge pull request #28 from mbari-org:kevinsbarnard/issue27

Remove MBARI hard-coded bits ([`6e11a9d`](https://github.com/mbari-org/vars-gridview/commit/6e11a9d99568c5b9147281512cde07400e5c4682))

* Remove MBARI hard-coded bits
Fixes #27 ([`4010e79`](https://github.com/mbari-org/vars-gridview/commit/4010e79bf708b89831e7afa9d065779edd4d3c65))


## v0.3.3 (2023-08-19)

### Unknown

* Bump version ([`7dbaf74`](https://github.com/mbari-org/vars-gridview/commit/7dbaf748389a0ededccfb5c293c95251d1f63f08))

* Restore missing sort methods ([`d69c1a3`](https://github.com/mbari-org/vars-gridview/commit/d69c1a3f4112471dcf4fb5771b399ed57f3f1221))

* Fix #26 ([`9127bd6`](https://github.com/mbari-org/vars-gridview/commit/9127bd6091302f2e70152f9dfb5212b26d7c5697))


## v0.3.2 (2023-08-02)

### Unknown

* Bump version ([`1a9216e`](https://github.com/mbari-org/vars-gridview/commit/1a9216e5ba5621aeb72bb3e03c4ec3e38a4a488f))

* Fix camera platform filter ([`b2d31d3`](https://github.com/mbari-org/vars-gridview/commit/b2d31d32b0d076a931eb22f75c0e7eba4e2893b4))

* Remove DISTINCT from query ([`b6d32a8`](https://github.com/mbari-org/vars-gridview/commit/b6d32a8af1fca7d16acf0e8ec915ddf2b00f4bea))

* Merge branch &#39;develop&#39; into feature/activity-observation-group-query ([`063f9a0`](https://github.com/mbari-org/vars-gridview/commit/063f9a086da5c4cac6bdcd313f7a12d1707f4147))


## v0.3.1 (2023-08-02)

### Unknown

* Bump version ([`eb47fb5`](https://github.com/mbari-org/vars-gridview/commit/eb47fb5b4683b233b6d369fbe4af9c952164190c))

* More filters, fixed query ([`9564f53`](https://github.com/mbari-org/vars-gridview/commit/9564f5370eb3c8f6dfb9c205bf22df5135613a3c))

* Support sorting by multiple values ([`0c84506`](https://github.com/mbari-org/vars-gridview/commit/0c845069ee15c14821a5af8408e3a1d6eb3f7cfd))


## v0.3.0 (2023-06-16)

### Unknown

* Bump version ([`f270091`](https://github.com/mbari-org/vars-gridview/commit/f270091a8b2387153e0ab102760b4a0276a4d3d7))

* Working! ([`63d3747`](https://github.com/mbari-org/vars-gridview/commit/63d37471b6f65f80f34db9219f784d01c73c81dc))

* Begin integration ([`98028c5`](https://github.com/mbari-org/vars-gridview/commit/98028c55d60254a59d627dbd204b7973c1d1decf))


## v0.2.8 (2023-06-14)

### Unknown

* Bump version ([`ca61b3a`](https://github.com/mbari-org/vars-gridview/commit/ca61b3a9d6ff29949028072fee0a320f9122d41a))

* Several fixes to MP4 finding ([`d8e9601`](https://github.com/mbari-org/vars-gridview/commit/d8e9601bd85409ca769d996efe3de293efe693e4))


## v0.2.7 (2023-06-09)

### Unknown

* Bump version ([`fde6ef2`](https://github.com/mbari-org/vars-gridview/commit/fde6ef2244b251a58e8cfda0effb5678c52683a0))

* Guard against invalid videos ([`f33cb6c`](https://github.com/mbari-org/vars-gridview/commit/f33cb6c625c3a72041a7a351253cc4885d2d454a))


## v0.2.6 (2023-06-09)

### Unknown

* Bumped version ([`b0eb1f2`](https://github.com/mbari-org/vars-gridview/commit/b0eb1f284452d4d32a10b9debb89679786dce962))

* Find MP4 from any video in sequence ([`d151607`](https://github.com/mbari-org/vars-gridview/commit/d15160704c6648cb2a6cb6e6c54661708bf41d89))


## v0.2.5 (2023-03-25)

### Unknown

* Bump version ([`5ef0656`](https://github.com/mbari-org/vars-gridview/commit/5ef0656ad12510bd4ba1e4b3c5e88319c202ea88))

* Reworked open video ([`72369d0`](https://github.com/mbari-org/vars-gridview/commit/72369d06c1ee06bd502bd518f656a5d0506a4e49))


## v0.2.4 (2023-03-23)

### Unknown

* Bump version ([`7fa34ae`](https://github.com/mbari-org/vars-gridview/commit/7fa34ae9d7f78dcb6cc8af79a6657fbb0fce7788))

* Support filter by video_sequence_name ([`1ab80fe`](https://github.com/mbari-org/vars-gridview/commit/1ab80fe6a274726ff6a0561f098076c133e9115a))


## v0.2.3 (2023-03-23)

### Unknown

* Bump version ([`d7df4a8`](https://github.com/mbari-org/vars-gridview/commit/d7df4a8bea1df84b1f618039c093f7c4ceeded37))

* Fix #14 with explicit search for mp4 video ([`2486b4d`](https://github.com/mbari-org/vars-gridview/commit/2486b4d698415938bedf07511ce162b6c3f07320))


## v0.2.2 (2023-03-14)

### Unknown

* Bump version ([`ecc3dcc`](https://github.com/mbari-org/vars-gridview/commit/ecc3dcc33e588fc8a11b6c618d84ce7b131baf22))

* Fix ctrl-click deselect #15 ([`c1d6689`](https://github.com/mbari-org/vars-gridview/commit/c1d66896349164dee107d49d73b72557eeb70dd7))


## v0.2.1 (2023-02-18)

### Unknown

* Bump version ([`8ce5c3c`](https://github.com/mbari-org/vars-gridview/commit/8ce5c3c444dbfd74d02ebbe39efcfccbb5c342c7))

* Fix QRect/QRectF nit ([`471b67c`](https://github.com/mbari-org/vars-gridview/commit/471b67cbfe7cc8d436ec53fa773dd198ae7b2e5e))


## v0.2.0 (2023-02-18)

### Unknown

* Bump version ([`247df2d`](https://github.com/mbari-org/vars-gridview/commit/247df2d4a6a00832fe8d2d444e842306798cbc10))

* Add lock to gitignore ([`c7ea183`](https://github.com/mbari-org/vars-gridview/commit/c7ea1835c0acc4e14358e713432fc97e68a5f54c))

* Reworked coloring scheme #6 ([`2ab11ba`](https://github.com/mbari-org/vars-gridview/commit/2ab11bac9ad553cc0cf6202d0686d3861c344e2c))

* Larger, bold font. Scales with zoom #8 ([`18e5ae1`](https://github.com/mbari-org/vars-gridview/commit/18e5ae1963eede739708eb213ee63185e7db2149))

* Add recorded time as default sort method ([`736c75c`](https://github.com/mbari-org/vars-gridview/commit/736c75c566bf26d805e55ddd0c3300805f85fd6b))

* Change &#34;hide labeled&#34; -&gt; &#34;hide verified&#34; ([`10f26fc`](https://github.com/mbari-org/vars-gridview/commit/10f26fc02c81262810480ddd7138536aa8586beb))

* Fix hide verified ([`f33ee35`](https://github.com/mbari-org/vars-gridview/commit/f33ee35e2762d81e0d346266894ab6d11a255a23))

* Add sort by association, observation, re-enable ([`6cfe65e`](https://github.com/mbari-org/vars-gridview/commit/6cfe65e96de1ad930dc9c714023b6e94206cd087))

* Fix missing import ([`14c5e4d`](https://github.com/mbari-org/vars-gridview/commit/14c5e4d2f014db52bc8bfcab8a5551a9cbe77a7a))

* Make ui a proper package, set login dialog width ([`3e1816c`](https://github.com/mbari-org/vars-gridview/commit/3e1816c6adc580eb6ffdaaddbb19de4ffe16c4db))

* Support for observation deletion #12 ([`9e6e92c`](https://github.com/mbari-org/vars-gridview/commit/9e6e92cb916b1034cde9e37314e9171f999f9963))

* Add logging to operations, support new endpoints ([`c427e86`](https://github.com/mbari-org/vars-gridview/commit/c427e86e6197f8c45d8fb6a4613a8e8a8300e59f))

* Add annosaurus endpoints ([`36fcf8e`](https://github.com/mbari-org/vars-gridview/commit/36fcf8ed117af758802b936119741f99c9aac17f))

* Add beholder client ([`0b7914e`](https://github.com/mbari-org/vars-gridview/commit/0b7914e1d610b35d35f661967a7f3f02b4a13020))

* Fix #4 ([`2dbde04`](https://github.com/mbari-org/vars-gridview/commit/2dbde047872428033e4f00bd7cb2de3db844bba1))

* Modify selection mechanism #5 ([`41d3671`](https://github.com/mbari-org/vars-gridview/commit/41d367101c4696fe1ce6b5f79280ddb739375b32))

* Begin reworking image mosaic ([`8a786ec`](https://github.com/mbari-org/vars-gridview/commit/8a786ecfbfa0492f9190aaba7fe6021db3c472e3))

* Reformat with black and isort ([`711dd98`](https://github.com/mbari-org/vars-gridview/commit/711dd98c91d4ebadd85630ab39242024b337016b))


## v0.1.1 (2023-02-04)

### Unknown

* Fix missing image reference UUID sort ([`ca1918d`](https://github.com/mbari-org/vars-gridview/commit/ca1918d501fe5828cfecb13b925105acca349cb9))

* Bump copyright year ([`3b94d5d`](https://github.com/mbari-org/vars-gridview/commit/3b94d5d7576323f29de6f05b52c1938a1e59f9bb))


## v0.1.0 (2022-11-09)

### Unknown

* Move from Bitbucket ([`3e1012b`](https://github.com/mbari-org/vars-gridview/commit/3e1012b553f23a8b7c2507e0b6370ab82aa289c9))

* Initial commit to mbari-org repo. Migrated from MBARI BitBucket ([`29a3cb4`](https://github.com/mbari-org/vars-gridview/commit/29a3cb414a43caac329e772a43ee7e0bef8dac28))

* Initial commit ([`db534f7`](https://github.com/mbari-org/vars-gridview/commit/db534f7397a2d8aab6c494a9e77948692447b807))

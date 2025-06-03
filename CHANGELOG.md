# CHANGELOG


## v0.22.1 (2025-06-03)

### Bug Fixes

- Tweak BulkConceptInputDialog with autocomplete and drag-and-drop support, restore single-concept
  constraint
  ([`6f4bdd2`](https://github.com/mbari-org/vars-gridview/commit/6f4bdd2e6b94f582e765255552fa2ae44fb7e8b1))


## v0.22.0 (2025-06-02)

### Bug Fixes

- Handle timezone for annotation datetime and avoid NoneType error in ancillary data
  ([`0dd094c`](https://github.com/mbari-org/vars-gridview/commit/0dd094ce473c91736bf14ea819bc50aa36e73844))

### Features

- Support bulk concept input, unify bulk input dialog for multiple item types
  ([`1f18ddd`](https://github.com/mbari-org/vars-gridview/commit/1f18dddf48a31239732e1eb7df0c97637db96240))

ref #103


## v0.21.5 (2025-06-02)

### Bug Fixes

- Add explicit ordering by index_recorded_timestamp in query
  ([`7319727`](https://github.com/mbari-org/vars-gridview/commit/73197273f9828c33e32f181ddef42ecf96d9b917))


## v0.21.4 (2025-05-20)

### Bug Fixes

- Scroll back to last position on delete
  ([`75fd7a1`](https://github.com/mbari-org/vars-gridview/commit/75fd7a1dc7e217a9decffd46358293ed393839ab))

#100


## v0.21.3 (2025-05-07)

### Bug Fixes

- Require beholder-client >= 0.3.1 for proper timeout, improve error handling for failed image
  fetch, fix box data not being pushed
  ([`7d5bba3`](https://github.com/mbari-org/vars-gridview/commit/7d5bba3e62966345cc0a8c0fd825f2f91ee40f46))


## v0.21.2 (2025-05-06)

### Bug Fixes

- Restore expected bbox observer/generator metadata updates
  ([`85eb14f`](https://github.com/mbari-org/vars-gridview/commit/85eb14fc164272879825a777b633d571166ed37b))

- keep `observer` as original - don't update `generator`


## v0.21.1 (2025-04-30)

### Bug Fixes

- Handle validation errors when creating observations and log warnings for invalid associations
  ([`d4d4846`](https://github.com/mbari-org/vars-gridview/commit/d4d484696273c0eead9b71690c46382bc349802d))


## v0.21.0 (2025-04-28)

### Bug Fixes

- Remove unused display flags
  ([`284d1d1`](https://github.com/mbari-org/vars-gridview/commit/284d1d1515b57d4949083fde0eb7677953a3bb18))

- Resolve RectWidget graphics unloading on re-query and pagination
  ([`575e69e`](https://github.com/mbari-org/vars-gridview/commit/575e69ecbefbb65050d8e08f41e3d2e3a73967a3))

### Features

- Add basic pagination
  ([`f1b105f`](https://github.com/mbari-org/vars-gridview/commit/f1b105fffd51b0572fbcec56b52ec5e7cce1588d))

- Add uuids, observation group to ancillary data pane; rework association data structure
  representation
  ([`61a926b`](https://github.com/mbari-org/vars-gridview/commit/61a926bb861e48ca66e9776b67a9e5672abda7b2))

see #98


## v0.20.0 (2025-04-25)

### Code Style

- `valid_box` -> `is_box_valid` ref
  ([`1daf0fd`](https://github.com/mbari-org/vars-gridview/commit/1daf0fdbdb58ade4a40344daae1dd4b01e20872c))

- Add type hints/docstrings for BoundingBoxAssociation methods and properties
  ([`67e5915`](https://github.com/mbari-org/vars-gridview/commit/67e5915583a65d08d9496b31c2c0c6869acacd39))

### Features

- Add checkmark for rects marked for training
  ([`62abca1`](https://github.com/mbari-org/vars-gridview/commit/62abca1061477bbb69e0c378e8bb61d41fc2176f))

#95

- Add options to hide training and non-training rects in the UI
  ([`04b19b0`](https://github.com/mbari-org/vars-gridview/commit/04b19b07c2474faef53c83ce2e6af5692ccaeede))

#97

- Add training mark/unmark buttons and new bbox JSON prop `tags`
  ([`5b29563`](https://github.com/mbari-org/vars-gridview/commit/5b29563977980f329d01e94a21ae9c0ff2fb5b4c))


## v0.19.3 (2025-02-28)

### Bug Fixes

- Apply image scaling to Skimmer request
  ([`84f7f44`](https://github.com/mbari-org/vars-gridview/commit/84f7f441ee13df4c260dc2c33c55fa5882ab4b2e))


## v0.19.2 (2025-02-26)

### Bug Fixes

- Ensure UUID conversion for observation UUID in ImageMosaic, fix bug with "None" observation
  observer
  ([`ac819ec`](https://github.com/mbari-org/vars-gridview/commit/ac819ec8f7c04e4713fecfc6d5d246b0a570074e))

- Improve error handling for image fetching and ROI creation
  ([`6a5e42b`](https://github.com/mbari-org/vars-gridview/commit/6a5e42be0d7d91705b83c49608776e92efb780b1))


## v0.19.1 (2025-02-25)

### Bug Fixes

- Update Sharktopoda 2 video open code
  ([`fe53f25`](https://github.com/mbari-org/vars-gridview/commit/fe53f25d218d9e0d4b7f26ee12403bee4a0dd08c))

- Use clip_vitb32 features via dreamsim to avoid DINO concatenation error
  ([`f395e50`](https://github.com/mbari-org/vars-gridview/commit/f395e50571de68d8b5381b78736ffcdb4f7113f8))

### Performance Improvements

- Skip image download when ROI detail image view is collapsed
  ([`895ad8f`](https://github.com/mbari-org/vars-gridview/commit/895ad8f34a3b68e404ff396306989f91d6a7b0ea))


## v0.19.0 (2025-02-25)

### Features

- Integrate Skimmer
  ([`63920ca`](https://github.com/mbari-org/vars-gridview/commit/63920ca2b7ae36e56633a9a74453c2cc24ec773e))

Squashed commit of the following:

commit 9d6f4dc6e51b5bfb5c02b20ba0a74214709265e1 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Mon Feb 24 16:08:38 2025 -0800

fix open video, relabel, load cancel

commit 0e0f68963ac1312f79f810d19fff67eb8e94e37b Author: Kevin Barnard <kbarnard@mbari.org>

Date: Mon Feb 24 16:07:22 2025 -0800

reduce zoom single step value from 20 to 10

commit 77d48a17e4a1c1e6b326c65f5a21047fce729431 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Mon Feb 24 12:15:46 2025 -0800

improve typing in operations module, add typing to needs_auth decorator

commit cf287ab9738dbf1f51eed68ceee43dcdd5db2d43 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Mon Feb 24 10:55:44 2025 -0800

add query_download method and update Row parsing in ImageMosaic

commit be50a61a9a7673532a819aa0826f4690e03c83bb Author: Kevin Barnard <kbarnard@mbari.org>

Date: Thu Feb 20 16:58:17 2025 -0800

refactor image cropping logic to use SkimmerClient and add pytest as a development dependency

commit 1396a12a6507b21a9dd5af8a1eff767eb56adf3d Author: Kevin Barnard <kbarnard@mbari.org>

Date: Thu Feb 20 16:47:07 2025 -0800

fix re-querying logic, remove failed login dialog

commit aa65e7f0ba9dbf2d146e2c859d2c9d81630bb7e9 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Thu Feb 20 16:02:59 2025 -0800

several changes

- Remove image caching mechanism - Improve typing all around - "localization" -> "association" -
  Make `username` a setting value - Make `gui_zoom` a setting value - Add typing to
  association_meta_sort decorator factory - Avoid re-creating image mosaic to preserve metadata -
  Refactors abound

commit 212002eb2f0fee15c67939029df518086bd3fa0c Author: Kevin Barnard <kbarnard@mbari.org>

Date: Thu Feb 20 09:38:23 2025 -0800

fix use of wrong image referenece UUID

commit 1541cafdc32d4d53509c7a7916a79b718f3a63d3 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 21:19:21 2025 -0800

add error handling for failed RectWidget init

commit 90a34403a6fb515f81db9a61be3a554c3166b614 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:41:09 2025 -0800

begin UI refactor

commit 7970e5a709554c9e62add616768ee0a5dd150aff Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:57:29 2025 -0800

rework image mosaic fetching to use concurrent ThreadPoolExecutor

commit 3bc66d2b8268348b45e473c6b641c69de4996a3c Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:56:43 2025 -0800

page queries

commit 30a5f32b60a12197a98f50564cf33dec4ece7c75 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:55:20 2025 -0800

rework fetch_image call for video frames

commit 8afe4f898a060e8ea6942c4a21ecf654c976dcb3 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:54:23 2025 -0800

modify get_roi method to include optional elapsed time parameter for Skimmer API requests

commit 287c5a098634ec87cdb066875f64a4f7d6088fd0 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Tue Feb 18 13:53:40 2025 -0800

add paginated query function for M3 API with TSV parsing

commit bc26c4c4ba3a887dab0b1ca08ce7a34a5966cf6b Author: Kevin Barnard <kbarnard@mbari.org>

Date: Fri Feb 14 09:35:05 2025 -0800

restore image scaling logic

commit 22f93a88934161948952d55d2d775df792a2c422 Author: Kevin Barnard <kbarnard@mbari.org>

Date: Thu Feb 13 14:46:54 2025 -0800

add initial skimmer integration


## v0.18.0 (2025-02-25)

### Features

- Integrate diskcache for improved caching management and remove legacy cache handling
  ([`e1ffd10`](https://github.com/mbari-org/vars-gridview/commit/e1ffd100169a190ce89361dffdbc59a2b33e32b2))


## v0.17.0 (2025-02-13)

### Bug Fixes

- Update settings management, refactor GUI settings into same file
  ([`ab0210a`](https://github.com/mbari-org/vars-gridview/commit/ab0210a18ccfd92b3356f6bd7f4dd49bc8427c2a))

### Features

- Add new sharpness sorting methods and update available sort names
  ([`ec0ec03`](https://github.com/mbari-org/vars-gridview/commit/ec0ec039a2c116375f8a9395eef71d7f82cf9dcd))

Thanks to @lonnylundsten for this contribution! #88

- Rename imageInfoList to imageInfoTree and update data handling; replace `dive_number` with
  `video_sequence_name`
  ([`2f49bc7`](https://github.com/mbari-org/vars-gridview/commit/2f49bc7b149950aef7b002c809dcce2263b5555a))

### Refactoring

- Significant refactor of entire codebase
  ([`5707d7b`](https://github.com/mbari-org/vars-gridview/commit/5707d7b0748cbeb16205b46c43ddd46a80326b92))


## v0.16.4 (2025-02-06)

### Bug Fixes

- Add missing pydantic dep
  ([`f3120cc`](https://github.com/mbari-org/vars-gridview/commit/f3120cc8f4535becc89c56c842f218c385113f21))

- Correct subprocess call syntax for macOS file browser
  ([`636eb68`](https://github.com/mbari-org/vars-gridview/commit/636eb68e15db2ac5935f7b5999417af2f00cf0f1))

### Chores

- Fix CI attempting to publish version behind latest release
  ([`3a5772c`](https://github.com/mbari-org/vars-gridview/commit/3a5772ccd122e61f19bb1387454b47b73f5583c3))


## v0.16.3 (2025-02-04)

### Bug Fixes

- Normalize UUIDs and video reference UUID to lowercase in image mosaic
  ([`5768ada`](https://github.com/mbari-org/vars-gridview/commit/5768ada058daaf15b409b35885c193a8f1145a1f))

#84

### Chores

- Migrate from Rye to uv for dependency management and update CI workflow
  ([`2dc3b89`](https://github.com/mbari-org/vars-gridview/commit/2dc3b891feb110e9cf5ca96ea0e324142ed46079))


## v0.16.2 (2025-02-04)

### Bug Fixes

- Update reference to boundingBoxInfoTree in MainWindow class, remove unused json import
  ([`8432fa5`](https://github.com/mbari-org/vars-gridview/commit/8432fa5610867cceba75bb70cf2a080eceb6ad17))

- Use get method for video_sequence_name and video_start_timestamp to handle missing keys
  ([`a9703e5`](https://github.com/mbari-org/vars-gridview/commit/a9703e5e7503800e8b0522b2318bc4aa4b08762d))

#86

### Chores

- Update CI workflow to use dist-wheel for artifact storage and retrieval
  ([`217c057`](https://github.com/mbari-org/vars-gridview/commit/217c0573a80056f2a4b64d94c6620b78e32338e6))

### Code Style

- Format code via Rye/Ruff
  ([`ab7a5e0`](https://github.com/mbari-org/vars-gridview/commit/ab7a5e037053a2753ec89848f7a429a68ef7ff8b))

### Documentation

- Add badges, updated install instructions to README
  ([`8b4a409`](https://github.com/mbari-org/vars-gridview/commit/8b4a4091f7ff22f9827ff852724f239a80d0e51f))

- Correct heading from 'Install' to 'Installation' in README
  ([`c544a98`](https://github.com/mbari-org/vars-gridview/commit/c544a98ab29da29a8529d4d6bcd40346cf3b4ca5))

- Update installation instructions and clarify project requirements in README
  ([`93ffe4d`](https://github.com/mbari-org/vars-gridview/commit/93ffe4d15f57f2f6b7faf16831eb989667f2a67c))

- Update note formatting in installation section of README
  ([`d8d8186`](https://github.com/mbari-org/vars-gridview/commit/d8d818640fddb7de77bcf4d331a44e702aff5d8b))


## v0.16.1 (2025-01-29)

### Bug Fixes

- Update RAZIEL_URL_DEFAULT to use HTTPS
  ([`aa3ff92`](https://github.com/mbari-org/vars-gridview/commit/aa3ff92cbbcf4b6d8736cfee7d1f1de76bef51e7))

### Chores

- Fix pyproject.toml
  ([`936d4bc`](https://github.com/mbari-org/vars-gridview/commit/936d4bc8ec51783071728d5edf338023d6fcac9e))

- Fix Rye path in CI
  ([`b406dc6`](https://github.com/mbari-org/vars-gridview/commit/b406dc6bec0b92ec6c75bdfd9a5747986c735681))

### Refactoring

- Use Rye
  ([`c8a8642`](https://github.com/mbari-org/vars-gridview/commit/c8a8642124943b4f04f36cb0fc00f32072d5d5f4))


## v0.16.0 (2025-01-28)

### Bug Fixes

- Ensure type consistency for query item fields in ImageMosaic
  ([`d9f2fff`](https://github.com/mbari-org/vars-gridview/commit/d9f2fffd6362eba7d44247a06879f338c3c0159c))

### Features

- Replace SQL with annosaurus query
  ([`6ad52d8`](https://github.com/mbari-org/vars-gridview/commit/6ad52d8f11a04be0e768d07499e887b97587a74f))

Remove SQL access #79

### Refactoring

- Add version variable in vars_gridview package init
  ([`083263c`](https://github.com/mbari-org/vars-gridview/commit/083263c0e1576f1923e030f0d3c458430a135cd5))


## v0.15.0 (2024-12-05)

### Bug Fixes

- Handle errors when creating embedding model in MainWindow
  ([`ac8f4b4`](https://github.com/mbari-org/vars-gridview/commit/ac8f4b413d3efba542d7553510bc8ceee22dcb74))

### Features

- Add new intensity and hue variance sort methods
  ([`b13875b`](https://github.com/mbari-org/vars-gridview/commit/b13875b91279b2fbf3b984a171ea1a6ef6cef9e4))


## v0.14.0 (2024-11-13)

### Features

- Add bulk input for UUIDs in query filters #81
  ([`d0420eb`](https://github.com/mbari-org/vars-gridview/commit/d0420eb4f35381d85fa4157a35a73084dabba9f7))


## v0.13.0 (2024-10-02)

### Documentation

- Add CI badge to readme
  ([`1aebfae`](https://github.com/mbari-org/vars-gridview/commit/1aebfae057187f78df7512a1907de838f95fbdca))

### Features

- Add LaplacianVarianceSort for sorting by sharpness
  ([`a8e2dee`](https://github.com/mbari-org/vars-gridview/commit/a8e2deecc1360b3792f9fed7c9acdcfc67758531))

- Added a new sorting method called LaplacianVarianceSort to the SortMethod class in
  sort_methods.py. - This sorting method calculates the Laplacian variance of the grayscale ROI of
  each RectWidget and uses it as the sorting key. - The Laplacian variance is calculated using the
  cv2.Laplacian function from the OpenCV library. - The SortDialog class in SortDialog.py was
  updated to include the new sorting method.


## v0.12.1 (2024-05-14)

### Performance Improvements

- Use best available torch backend for embedding
  ([`59dcc06`](https://github.com/mbari-org/vars-gridview/commit/59dcc06eaeaa6db7e833c55caf7d8871fdbbab73))

Automatically detect and use the best available backend for PyTorch. This is used to specify the
  device on which to compute the embeddings. Currently, this searches in order: 1. CUDA 2. MPS

If no device is available, this process will fall back on the CPU.


## v0.12.0 (2024-05-10)

### Features

- Add embedding sort
  ([`60798b2`](https://github.com/mbari-org/vars-gridview/commit/60798b2298d2abe931d15af5d7b5d9ec35f780da))

Requires a CUDA-enabled GPU.


## v0.11.0 (2023-12-21)

### Bug Fixes

- Grab focus in login dialog on startup
  ([`0995775`](https://github.com/mbari-org/vars-gridview/commit/0995775ffdd7f66c38364410669d7e4686194f2e))

- Open into log directory in macOS
  ([`aa6d37d`](https://github.com/mbari-org/vars-gridview/commit/aa6d37ddb5a6f369e298ce44e7d374fd3659881a))

- Update observation UUID constraint
  ([`946779f`](https://github.com/mbari-org/vars-gridview/commit/946779f5e238ca6e9a994b11bda6b50825a9132f))

### Features

- Add button to open log directory
  ([`a87b78e`](https://github.com/mbari-org/vars-gridview/commit/a87b78e028f6ef40e36921702595690b6260a3d9))


## v0.10.0 (2023-12-14)

### Bug Fixes

- Add all localizations from the same video into S2
  ([`99ea7a0`](https://github.com/mbari-org/vars-gridview/commit/99ea7a0a1d4a64ce20bd83bef224d2b61d1d9a12))

- Reset to recorded timestamp sort on new query
  ([`a8144cc`](https://github.com/mbari-org/vars-gridview/commit/a8144cc039ca59a4f6e659da74ab6200f935c949))

### Features

- Add verifier and verified query filters
  ([`d94ab98`](https://github.com/mbari-org/vars-gridview/commit/d94ab98a2d0cd461b5bf17b520bb82311754bb61))


## v0.9.0 (2023-12-13)

### Bug Fixes

- Add error dialog when saving localizations fails
  ([`cf92bb3`](https://github.com/mbari-org/vars-gridview/commit/cf92bb3a9887a073599c268c2009baf66fe07785))

- Maintain sort across updates
  ([`29e6483`](https://github.com/mbari-org/vars-gridview/commit/29e648386cb6d0592b4bd498dc02b201730e4140))

Related to #49

- Maintain sort options in dialog, don't auto re-sort
  ([`abfd1b9`](https://github.com/mbari-org/vars-gridview/commit/abfd1b94e7c1309e07a07abdd8dc989ba21e18cc))

### Chores

- Add macOS build script
  ([`b0ba51f`](https://github.com/mbari-org/vars-gridview/commit/b0ba51fe96b4b0e845479052d70ed740c68de279))

### Features

- Add "hide unverified" button
  ([`52b477d`](https://github.com/mbari-org/vars-gridview/commit/52b477d6809262b7d9f8e9f1d32207ed64e4fcc3))

Closes #55

- Add sort by confidence
  ([`151f8b9`](https://github.com/mbari-org/vars-gridview/commit/151f8b92c536e5d7c7be5d71cb1aa6673d8c1a30))

Closes #63


## v0.8.1 (2023-12-12)

### Bug Fixes

- Fix parsing of native timestamp with tzoffset
  ([`2cf39f2`](https://github.com/mbari-org/vars-gridview/commit/2cf39f250d572b194258ba9d1529e86c995bf950))

- Run 'open -a' command when showing in S2
  ([`5cf7307`](https://github.com/mbari-org/vars-gridview/commit/5cf7307cfa78989c5b12ef11c5001e027fde6dc5))

On macOS, call 'open -a' to open Sharktopoda 2 (or bring it to the forefront if it's already open)
  when showing a localization. (#42)

- Turn off touch events re: macOS QTBUG-103935
  ([`3bfc0d7`](https://github.com/mbari-org/vars-gridview/commit/3bfc0d76b14e4eba4cbc3de0c7574193840c7bde))

Set attribte WA_AcceptTouchEvents to false in GraphicsViews. See QTBUG-103935 for details.

This resolves the "qt.pointer.dispath: Skipping QEventPoint" message spam issue in the terminal.

### Chores

- Add macOS codesign identity/bundle ident
  ([`2a9b03d`](https://github.com/mbari-org/vars-gridview/commit/2a9b03d810888a45bfd1bf56efca80f15b8f105b))


## v0.8.0 (2023-12-05)

### Bug Fixes

- Bring S2 video window top-level
  ([`340601a`](https://github.com/mbari-org/vars-gridview/commit/340601a65f6220058bdfea7cf53a44f222044e5c))

Invoke the `show` command in Sharktopoda 2 when a localization is shown. Closes #42

### Code Style

- Improve spacing, borders in grid view
  ([`f95787a`](https://github.com/mbari-org/vars-gridview/commit/f95787ab88b10543eb1d556bc2d0436ca65c2f94))

Closes #41

### Features

- Add sort by verifier
  ([`d785f04`](https://github.com/mbari-org/vars-gridview/commit/d785f0403eccd046644a44685e25efb4082e7bbb))

Closes #53


## v0.7.0 (2023-12-04)

### Bug Fixes

- Fix default value assign in SettingProxy init
  ([`e7b27e8`](https://github.com/mbari-org/vars-gridview/commit/e7b27e8be053d9fb1ccf2e824906cae8b09cc45a))

- Make annotation detail info read-only
  ([`45516f0`](https://github.com/mbari-org/vars-gridview/commit/45516f0941dfceb277ea9d1a4c7ac75afb1efecb))

### Chores

- Reindent gridview.ui
  ([`04b5b11`](https://github.com/mbari-org/vars-gridview/commit/04b5b11e3f18dc0dbe9b9be8febe0f9f6aaa53d4))

### Features

- Add Sharktopoda autoconnect setting
  ([`4ab6463`](https://github.com/mbari-org/vars-gridview/commit/4ab646324743ac07b38f2fc9dfd7d001937e7827))

Defaults to on.

- Add un/verify buttons, refactor label logic
  ([`551857c`](https://github.com/mbari-org/vars-gridview/commit/551857cd23c078048b48cf23c9d513f3599d2635))


## v0.6.0 (2023-12-01)

### Bug Fixes

- Enable manifest file indentation
  ([`94f9541`](https://github.com/mbari-org/vars-gridview/commit/94f9541dbfeebda8a6922d3a47b65d35c6e94d10))

### Chores

- Pin poetry-publish to semantic-release tag
  ([`eb8cb62`](https://github.com/mbari-org/vars-gridview/commit/eb8cb62180d62f672d4a93c7f18560639ecb3c0e))

### Features

- Add cache controller and settings UI
  ([`22a0e15`](https://github.com/mbari-org/vars-gridview/commit/22a0e15f5d31619b860d4fa6cc67ce57e62afb8c))

- Integrate initial image caching
  ([`62637f5`](https://github.com/mbari-org/vars-gridview/commit/62637f5ba38ff2816c2d384cb1447a143ff69d7a))


## v0.5.4 (2023-11-30)

### Bug Fixes

- Fix observation observer value parsing
  ([`06802fd`](https://github.com/mbari-org/vars-gridview/commit/06802fde1ac2261f77885907569b9f7bb5d1de7d))

Previously, the "Observation observer" field in the details list was being incorrectly populated.

### Chores

- Fix Poetry publish in CI
  ([`d4cefba`](https://github.com/mbari-org/vars-gridview/commit/d4cefba3aa03af3079254242c9ee9a44e9eab7cf))

### Code Style

- Update window title to include version
  ([`c6a50d5`](https://github.com/mbari-org/vars-gridview/commit/c6a50d5eb47f058b8f52a3a9d27f4203c1d465fa))

e.g. "VARS GridView v0.5.4"


## v0.5.3 (2023-11-30)

### Bug Fixes

- Pin TDS version back to 7.0
  ([`dd64838`](https://github.com/mbari-org/vars-gridview/commit/dd64838db9944a69ce2ccc3265c0997acead2d32))

pymssql with TDS 7.3 parses datetime2 as datetime, leading to a drop in timestamp resolution (100 ns
  -> ~3 ms). This causes incorrect frames to occasionally be grabbed from Beholder.


## v0.5.2 (2023-11-29)

### Bug Fixes

- Pin TDS version to 7.3
  ([`12af446`](https://github.com/mbari-org/vars-gridview/commit/12af44648a3f2653deec53aa973ebb5f8a7663da))

### Chores

- Update CI workflow to include poetry publishing
  ([`777066d`](https://github.com/mbari-org/vars-gridview/commit/777066d042a026e732aa8a7299766b48310128c9))

Remove pyinstaller build/release for now


## v0.5.1 (2023-11-28)

### Bug Fixes

- Sharktopoda resize calculation
  ([`f5a7716`](https://github.com/mbari-org/vars-gridview/commit/f5a771666f5e56e83a1a5860ac4da4a554fb140d))


## v0.5.0 (2023-11-27)


## v0.4.8 (2023-11-27)


## v0.4.7 (2023-11-21)


## v0.4.6 (2023-11-20)


## v0.4.5 (2023-11-16)


## v0.4.4 (2023-11-16)


## v0.4.3 (2023-11-14)


## v0.4.2 (2023-11-13)


## v0.4.1 (2023-11-13)


## v0.4.0 (2023-11-13)


## v0.3.17 (2023-11-13)


## v0.3.16 (2023-11-07)


## v0.3.15 (2023-11-07)


## v0.3.14 (2023-10-04)


## v0.3.13 (2023-10-04)


## v0.3.12 (2023-10-04)


## v0.3.11 (2023-10-04)


## v0.3.10 (2023-09-26)


## v0.3.9 (2023-09-25)


## v0.3.8 (2023-09-25)


## v0.3.7 (2023-08-22)


## v0.3.6 (2023-08-22)


## v0.3.5 (2023-08-21)


## v0.3.4 (2023-08-18)


## v0.3.3 (2023-08-18)


## v0.3.2 (2023-08-01)


## v0.3.1 (2023-08-01)


## v0.3.0 (2023-06-15)


## v0.2.8 (2023-06-13)


## v0.2.7 (2023-06-08)


## v0.2.6 (2023-06-08)


## v0.2.5 (2023-03-24)


## v0.2.4 (2023-03-22)


## v0.2.3 (2023-03-22)


## v0.2.2 (2023-03-13)


## v0.2.1 (2023-02-17)


## v0.2.0 (2023-02-17)


## v0.1.1 (2023-02-03)


## v0.1.0 (2022-11-08)

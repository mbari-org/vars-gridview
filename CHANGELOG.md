# CHANGELOG


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

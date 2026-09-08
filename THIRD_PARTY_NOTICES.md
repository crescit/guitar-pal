# Third-party notices

This file records the provenance of assets shipped in this repository. It is not a substitute for reviewing the licenses of packages installed by `pip` or for legal advice.

## Guitar-Analyzer model weights

The following unmodified weights come from [MaksymMaryniuk/Guitar-Analyzer](https://github.com/MaksymMaryniuk/Guitar-Analyzer/tree/master/models):

| Local file | SHA-256 | Upstream Git blob |
| --- | --- | --- |
| `models/Finger-Pose2.pt` | `88f619567b3e2b1b9a764af722e38046abcfc9507a726b7baf1fb143474d9bda` | `f036a5775fdb19e8760698e343a39bd6ecec6107` |
| `models/Guitar-Detection.pt` | `915b429fcb8c4e456ae759ff1b56e9290274a864941a1ef5618c7233653762bd` | `c2edb455b8008cd39c4be06b0c59084ada878994` |
| `models/Neck-Keypoints.pt` | `c0d59e07a464fa6c355db58da33d00de23fd0ef005a34ac2b0e9b96a2b48311c` | `ccfc028b98d90445cb61a187df18f2329a568fe8` |

Copyright © 2026 Maksym Maryniuk. Licensed under the MIT License. The required license and copyright notice are retained in [`licenses/Guitar-Analyzer-MIT.txt`](licenses/Guitar-Analyzer-MIT.txt).

Parts of `src/guitar_detector.py` were adapted from the same project and are redistributed under the repository's AGPL-3.0-or-later license, which is compatible with the upstream MIT grant. The upstream copyright and permission notice remain applicable.

## MediaPipe Hand Landmarker

`models/hand_landmarker.task` is the unmodified float16 Hand Landmarker bundle downloaded from Google's [official MediaPipe model endpoint](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task).

- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- MediaPipe source and license: [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe)
- License text: [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt)

MediaPipe is licensed under Apache-2.0. Its distribution also contains a `NOTICE` file; when redistributing the MediaPipe package itself, retain the license and notice installed with that package.

## Ultralytics

The project imports the `ultralytics` Python package and loads YOLO-format weights through it. The package is not vendored here, but it is a required dependency for `src/guitar_detector.py` and is licensed under AGPL-3.0 (with commercial licensing available separately). To avoid presenting a permissive license that conflicts with Ultralytics' published open-source conditions, Guitar Buddy is distributed under AGPL-3.0-or-later.

See the [Ultralytics licensing documentation](https://docs.ultralytics.com/#yolo-licenses-how-is-ultralytics-yolo-licensed) and the license bundled with the installed package for the terms that apply to your use.

## Other Python dependencies

`requirements.txt` names dependencies fetched from their respective package indexes; their source distributions are not copied into this repository. The direct dependencies were reviewed on 2026-09-08 as follows:

| Dependency | Declared license |
| --- | --- |
| `opencv-python-headless` | Apache-2.0 |
| `numpy` | BSD-3-Clause, with separately licensed bundled components |
| `mediapipe` | Apache-2.0 |
| `ultralytics` | AGPL-3.0 |
| `scipy` | BSD-3-Clause, with separately licensed bundled components |
| `mido` | MIT |

Each dependency remains governed by its own license, and binary wheels can include additional notices for bundled native libraries. Preserve the license files installed with those packages when you redistribute an environment, executable, container image, or wheel. Recheck this inventory when changing dependency versions.

## Reference projects

[nathanchiu05/Computer-Vision-Guitar-Tutor](https://github.com/nathanchiu05/Computer-Vision-Guitar-Tutor) informed early research, but this repository does not include its source code or assets. Acknowledgment does not incorporate that repository into this distribution.

## Media policy

The project does not ship third-party guitar recordings or videos. Files under `data/audio/` and `data/videos/` are local inputs supplied by the user and are excluded from version control. Only add or redistribute media when you own it or have a license that permits the intended distribution.

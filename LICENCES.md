# Licences

## Kit code

MIT License (see `LICENSE`), Copyright (c) 2026 Chalkboard Explainer contributors.

(Everything under `code/`, `config/` and `examples/` was written for this kit. The hand sprite is
drawn procedurally by `code/chalkkit/hand_sprite.py`, so it uses no third-party image.)

## Bundled assets

All of these can be redistributed and used commercially. Each licence was checked at its source on 2026-10-13.

| File | Source | Author | Licence | Modified? |
|---|---|---|---|---|
| `assets/fonts/PermanentMarker-Regular.ttf` | https://github.com/google/fonts/tree/main/apache/permanentmarker (Google Fonts "Permanent Marker") | Font Diner, Inc. | Apache License 2.0 (`assets/fonts/LICENSE-PermanentMarker-Regular.txt`) | No, byte-identical to the google/fonts copy |
| `assets/fonts/WalterTurncoat-Regular.ttf` | https://github.com/google/fonts/tree/main/apache/walterturncoat (Google Fonts "Walter Turncoat") | Font Diner, Inc. DBA Sideshow | Apache License 2.0 (`assets/fonts/LICENSE-WalterTurncoat-Regular.txt`) | No, byte-identical to the google/fonts copy |
| `assets/sfx/scratch_pool.wav` | Made from Freesound 264944 "Chalk on chalkboard.wav" (https://freesound.org/people/fattirewhitey/sounds/264944/) and Freesound 751870 "Chalkboard" (https://freesound.org/people/TimOut789/sounds/751870/) | fattirewhitey; TimOut789 | CC0 1.0 (public domain dedication) | Yes: denoised, high-passed, trimmed to active scratch, crossfaded, transients softened, levelled, resampled to 48 kHz mono |
| `assets/sfx/tap.wav` | Made from Freesound 447925 "Write/Draw with chalk on board" (https://freesound.org/people/Breviceps/sounds/447925/) | Breviceps | CC0 1.0 | Yes: one 70 ms onset cut out, 1.8 kHz high-pass, decay envelope, 48 kHz mono |

The kit does not ship the original recordings. `code/tools/prepare_samples.py` downloads their
public preview MP3s again and rebuilds the processed files. Attribution is not required for CC0
or for using these fonts in videos, but a credit is a kind thing to give:
"Chalk sounds: fattirewhitey, TimOut789, Breviceps (Freesound, CC0)".

The rendered videos include font outlines. Apache-2.0 fonts may be used in commercial video with no restriction.

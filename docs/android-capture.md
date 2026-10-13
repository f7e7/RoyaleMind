# First Android Screenshot Capture

This is a Phase 1 read-only capture procedure. A phone is not needed for offline tests or
metadata validation. The command does not launch or control the game.

1. Activate the installed environment: `source .venv/bin/activate`. Confirm `royalemind health`
   reports ADB available. If ADB is missing, install Android Platform Tools manually as described
   in the README, then rerun the health check.
2. On the phone, enable Developer options and USB debugging manually. Connect a data-capable USB
   cable, unlock the phone, and approve that computer's debugging prompt. Do not grant access on
   an untrusted computer.
3. Run `royalemind devices`. Copy the serial from the `device (authorized)` line. If it says
   `unauthorized`, approve the phone prompt; if `offline`, reconnect the cable and rerun the
   command. If no device appears, check the cable, USB mode, Android Platform Tools, and local
   USB permissions. This diagnostic only runs `adb devices -l`.
4. Manually open the desired game screen and remove personal identifiers from view if possible.
   Note the device model, game version, orientation, game mode, and UI/layout condition separately;
   RoyaleMind cannot verify these from image bytes.
5. Run `royalemind capture-frame --serial YOUR_DEVICE_SERIAL --output-dir data/captures` once per
   desired frame. It runs only `adb -s SERIAL get-state` and
   `adb -s SERIAL exec-out screencap -p`. A successful command prints the image and JSON sidecar
   paths. The filename includes a UTC timestamp and random suffix, and exclusive file creation
   prevents overwriting earlier captures.
6. Inspect the saved image and sidecar. The sidecar records the host capture timestamp in UTC,
   selected ADB serial in `source`, image dimensions and format, freshness, SHA-256, and capture
   method. The timestamp is recorded after the screenshot command returns, so it is not an exact
   device exposure time. Device model, game version, mode, and annotation labels remain manual
   provenance; do not infer them from the sidecar. Keep private captures under ignored `data/`.
7. Collect representative layouts and conditions before Phase 2 evaluation, then annotate an
   approved subset. Audit the resulting dataset with
   `royalemind audit-dataset /path/to/approved/dataset --output data/reports/dataset-inspection.json`.

For capture errors, run `royalemind devices` again. An absent executable, unauthorized/offline
device, timeout, empty screenshot, and malformed image all produce nonzero status with diagnostics.
No model weights or detector are required for capture.

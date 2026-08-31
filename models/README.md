# Third-party model weights

## fire.pt - fire and smoke detection

Classes: `fire`, `smoke`. YOLOv8n, 150 epochs, trained 2024-08-29.

Source: https://github.com/luminous0219/fire-and-smoke-detection-yolov8
(`weights/best.pt`, AGPL-3.0, 6,262,051 bytes)
Upstream sha256: `ac0a10257b2bc1f20c9d957f8adeeb61dd6140322fc19d0b4a116cb491776d16`

**This file is not the download.** A `.pt` is a Python pickle, and
`torch.load` executes what it contains - the standard supply-chain attack on
ML models. Before trusting it:

1. `scan_pickle.py` disassembles the pickle with `pickletools.genops`, which
   parses opcodes without importing or calling anything, and lists every
   global the checkpoint would reach for. Result: 22 of 23 were stock
   torch/ultralytics; the odd one out was `dill._dill._load_type`, called with
   the single argument `"set"` to rebuild `_non_persistent_buffers_set`. No
   code-object constructors anywhere.
2. `sanitise.py` then loaded it once in a container with `--network none`, no
   credentials and no volumes, shimmed `dill` with an allowlist of six
   builtin types, and re-saved the checkpoint.

`fire.pt` here is that re-export: pickled by us, from an audited object graph,
with no dill dependency. To re-verify, run `scan_pickle.py` against it.

## Known behaviour

Tested against `samples/drone/`, which is synthetic - so this measures very
little, and is recorded only to show it is not a settled question:

    drone-crop-fire-01.jpg   -> nothing              (missed)
    drone-crop-fire-02.jpg   -> fire 0.534, 0.327
    drone-field-flood-01.jpg -> nothing              (correct)
    drone-field-flood-02.jpg -> fire x5, 0.26-0.48   (false positives on water)

It has never been evaluated on real fire footage here. Treat the accuracy as
unknown until it has been.

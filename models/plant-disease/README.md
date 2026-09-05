# plant-disease: leaf disease detection

30 PlantDoc classes across 13 crops. Source:
[nickmuchi/yolos-small-plant-disease-detection](https://huggingface.co/nickmuchi/yolos-small-plant-disease-detection)
(YOLOS-small, trained on PlantDoc: 2,569 images, 13 species, 17 diseases).

A **transformers** detection model, not Ultralytics weights, since leaf
disease is only published in that form. That's why `detector.py` grew a
second model family. Loaded via `HF_MODELS=plant=/models/plant-disease`.

## Provenance

Upstream shipped `pytorch_model.bin`, a pickle. As with `fire.pt` it was
disassembled before loading (`../scan_pickle.py`):

    3 distinct globals: collections.OrderedDict, torch.FloatStorage,
                        torch._utils._rebuild_tensor_v2

A plain state dict with no custom classes, the cleanest of the three
third-party checkpoints here. It was then converted to `model.safetensors`,
which was necessary as well as safer: transformers 5.x refuses to load `.bin`
under torch < 2.6 (CVE-2025-32434).

Upstream sha256 of the original .bin:
`b08b889722550ba42a5e3655fa688d32080613b13ae42f3e19a868b8d640d2f3`

## Measured behaviour

Against `samples/plant/`, reporting every prediction above 0.05 rather than
only what passes a threshold:

    corn-leaf-blight-01.png      0.971  Corn leaf blight          correct
    corn-leaf-blight-02.png      0.902  Corn leaf blight          correct
    corn-leaf-healthy-01.png     0.697  Corn leaf blight          FALSE POSITIVE
    tomato-leaf-blight-01.png    0.939  Potato leaf late blight   right disease, wrong crop
    tomato-leaf-blight-02.png    0.569  Potato leaf late blight   right disease, wrong crop
    tomato-leaf-healthy-01.png   0.831  Tomato leaf               correct

Three things follow, and the rules are built around them.

**There is no healthy-corn class.** PlantDoc has `Corn leaf blight`,
`Corn Gray leaf spot` and `Corn rust leaf` but nothing for a healthy corn
leaf, so a healthy leaf must be called diseased or nothing at all. It scores
0.697, above the old global 0.65. The corn rule therefore sits at **0.80**,
which the two real blights clear (0.97, 0.90) and the healthy leaf does not.

**Tomato blight is reported as `Potato leaf late blight`.** Not a bug worth
fixing: tomato and potato are both Solanaceae and late blight is the same
pathogen (*Phytophthora infestans*) with the same lesions on both. The model
gets the disease right and the host wrong. The rule matches on the label the
model actually emits.

**Scores run lower than COCO's.** A genuine tomato blight sits at 0.569,
which the global `MIN_CONFIDENCE=0.65` would have discarded before any rule
saw it, so the detection would simply never have appeared. Hence
`MODEL_CONFIDENCE`, and this model's floor of 0.40.

## What it is not

Disease needs a leaf filling the frame; lesions are millimetres across and are
not present in a wide field shot. `plant-camera` is an inspection bench, not
surveillance. The honest production shape is an upload endpoint — photograph a
suspect leaf, get an answer — not an RTSP feed.

Six images is a small evaluation set. Treat these numbers as a first
measurement, not a specification.

"""
Load the downloaded checkpoint once, in isolation, and re-serialise it.

Two problems solved at the same time:

1. The checkpoint calls dill._dill._load_type("set") to rebuild a stock
   PyTorch attribute. We do not want dill as a runtime dependency of
   ai-service just for that, so we shim it - with an allowlist, not a
   passthrough. A passthrough shim would happily hand back os.system if a
   different checkpoint asked for it.

2. Re-saving means the weights ai-service loads were pickled HERE, by us,
   from an already-audited object graph. The original vendor pickle never
   gets loaded again.
"""
import builtins
import sys
import types

# torch is imported FIRST, deliberately. It probes for dill at import time
# (torch.utils.data.datapipes calls find_spec("dill")), and a hand-made module
# object has no __spec__, so installing the shim first makes torch itself blow
# up. Import torch, then shim - torch.load resolves the name later, at unpickle
# time, which is all we need.
import torch

# The only types a checkpoint has any business reconstructing this way.
ALLOWED = {"set", "frozenset", "list", "dict", "tuple", "bytes", "type"}


def _load_type(name):
    if name not in ALLOWED:
        raise RuntimeError(f"refusing to reconstruct type {name!r}")
    return getattr(builtins, name)


dill = types.ModuleType("dill")
dill._dill = types.ModuleType("dill._dill")
dill._dill._load_type = _load_type
sys.modules["dill"] = dill
sys.modules["dill._dill"] = dill._dill

# weights_only=False is safe here only because the opcode audit already ran
# and this container has no network and no credentials.
ckpt = torch.load("/work/fire.pt", map_location="cpu", weights_only=False)
print("checkpoint keys:", sorted(ckpt.keys()))

model = ckpt.get("model")
print("class names:", getattr(model, "names", None))
print("epoch:", ckpt.get("epoch"), " trained on:", ckpt.get("date"))

torch.save(ckpt, "/work/fire_clean.pt")
print("re-saved to /work/fire_clean.pt")

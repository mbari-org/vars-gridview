from abc import ABC
from pathlib import Path

import numpy as np
import torch
from dreamsim import dreamsim
from PIL import Image
from torch.types import Device

from vars_gridview.lib.constants import SETTINGS

# Patch torch.hub._validate_not_a_forked_repo to avoid error while downloading weights
torch.hub._validate_not_a_forked_repo = lambda *_: True


def get_torch_device() -> Device:
    """
    Get the appropriate torch device for embedding computation.

    Returns:
        Device: torch device instance.
    """
    # Define an ordered list of predicates to check the device availability and its corresponding device string
    device_check_order = [
        (torch.cuda.is_available, "cuda"),
        (torch.backends.mps.is_available, "mps"),
    ]

    # Check each predicate in order, returning the first device that is present
    for check, device_str in device_check_order:
        present = check()
        if present:
            return device_str

    # Failing all, use CPU
    return "cpu"


class Embedding(ABC):
    """
    Embedding abstract base class. Produces embedding vectors for images.
    """

    def embed(self, image: np.ndarray) -> np.ndarray:
        """
        Embed an image.

        Args:
            image (np.ndarray): Image as an RGB (h,w,3) Numpy array.

        Returns:
            np.ndarray: Vector embedding (n,) for the image.
        """
        raise NotImplementedError()


class DreamSimEmbedding(Embedding):
    """
    DreamSim embedding.
    """

    CACHE_SUBDIR_NAME = "dreamsim"

    def __init__(self) -> None:
        base_cache_dir = Path(SETTINGS.cache_dir.value)
        dreamsim_cache_dir = base_cache_dir / DreamSimEmbedding.CACHE_SUBDIR_NAME

        # Get the appropriate torch device
        self._device = get_torch_device()

        # Download / load the models
        self._model, self._preprocess = dreamsim(
            pretrained=True,
            device=self._device,
            cache_dir=str(dreamsim_cache_dir.resolve().absolute()),
            dreamsim_type="clip_vitb32",
        )

    def embed(self, image: np.ndarray) -> np.ndarray:
        # Preprocess the image
        image_pil = Image.fromarray(image)
        image_tensor = self._preprocess(image_pil).to(self._device)

        # Compute the embedding
        embedding = self._model.embed(image_tensor).cpu().detach().numpy().flatten()
        return embedding

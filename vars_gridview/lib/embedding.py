from abc import ABC
from pathlib import Path

import numpy as np
from dreamsim import dreamsim
from PIL import Image

from vars_gridview.lib.settings import SettingsManager


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
        settings = SettingsManager.get_instance()
        base_cache_dir = Path(settings.cache_dir.value)
        dreamsim_cache_dir = base_cache_dir / DreamSimEmbedding.CACHE_SUBDIR_NAME

        # Download / load the models
        self._model, self._preprocess = dreamsim(
            pretrained=True,
            device="cuda",
            cache_dir=str(dreamsim_cache_dir.resolve().absolute()),
        )

    def embed(self, image: np.ndarray) -> np.ndarray:
        # Preprocess the image
        image_pil = Image.fromarray(image)
        image_tensor = self._preprocess(image_pil).cuda()

        # Compute the embedding
        embedding = self._model.embed(image_tensor).cpu().detach().numpy().flatten()
        return embedding

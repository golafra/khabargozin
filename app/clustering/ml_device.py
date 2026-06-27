"""Pick CPU or CUDA for sentence-transformers models."""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ml_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            logger.info("Using GPU for ML models: %s", torch.cuda.get_device_name(0))
            return "cuda"
    except ImportError:
        pass
    logger.info("Using CPU for ML models")
    return "cpu"

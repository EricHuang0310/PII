"""Pipeline orchestration — the `mask()` entry point and dialogue wrappers."""

from pii_masker.pipeline.masker import MaskingPipeline, mask
from pii_masker.pipeline.dialogue import mask_dialogue

__all__ = ["MaskingPipeline", "mask", "mask_dialogue"]

"""Analysis modules — the use-case-agnostic seam (Phase 5).

Adapters preprocess (windowed reads, DN->physical, quality masks); modules
in this package turn a SceneWindow into metric values. `runner` finds
(scene, aoi) pairs missing metrics and writes them — self-healing, so a
crashed sweep is repaired by the next one.
"""

"""On-the-fly map tiles from provider COGs — rendered per request, cached
in-process, nothing stored. This is the TiTiler approach without running a
second service: same windowed reads, same hardware.
"""

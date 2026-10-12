"""Caché de tiles: el registro se dibuja por franjas horizontales que se reutilizan.

Mover el cursor o desplazarse ya no vuelve a dibujar todas las curvas: sólo se copian
imágenes ya hechas y se dibujan las franjas nuevas que aparecen.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtGui import QPixmap

TILE_H = 256  # alto de un tile en píxeles lógicos
MAX_BYTES = 160 * 1024 * 1024


class TileCache:
    def __init__(self, max_bytes: int = MAX_BYTES):
        self.max_bytes = max_bytes
        self._tiles: OrderedDict[int, QPixmap] = OrderedDict()
        self._bytes = 0
        self._key = None

    def validate(self, key) -> None:
        """Si cambia algo que afecta al dibujo (layout, escala, ancho, dpr…), se descarta todo."""
        if key != self._key:
            self.clear()
            self._key = key

    def clear(self) -> None:
        self._tiles.clear()
        self._bytes = 0

    def get(self, index: int) -> QPixmap | None:
        pm = self._tiles.get(index)
        if pm is not None:
            self._tiles.move_to_end(index)
        return pm

    def put(self, index: int, pm: QPixmap) -> None:
        self._tiles[index] = pm
        self._bytes += _size(pm)
        while self._bytes > self.max_bytes and len(self._tiles) > 1:
            _, old = self._tiles.popitem(last=False)
            self._bytes -= _size(old)

    def __contains__(self, index: int) -> bool:
        return index in self._tiles

    def __len__(self) -> int:
        return len(self._tiles)


def _size(pm: QPixmap) -> int:
    return pm.width() * pm.height() * 4

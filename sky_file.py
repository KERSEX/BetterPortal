# Erzeugen und Lesen von .sky-Dateien - exakt wie RPCS3 (rpcs3qt/skylander_dialog.cpp)
import struct

SKY_SIZE = 0x40 * 0x10  # 1024 Bytes (64 Bloecke x 16 Bytes, Mifare-1K-Layout)


def _make_crc_table():
    table = []
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
        table.append(crc & 0xFFFF)
    return table


_CRC_TABLE = _make_crc_table()


def crc16(data, init=0xFFFF):
    crc = init
    for b in data:
        crc = ((crc << 8) ^ _CRC_TABLE[((crc >> 8) ^ b) & 0xFF]) & 0xFFFF
    return crc


def create_sky_bytes(sky_id, sky_var):
    """Erzeugt den 1024-Byte-Inhalt einer .sky-Datei, byte-identisch zu RPCS3s 'Create'."""
    buf = bytearray(SKY_SIZE)
    # Block-Berechtigungen (Sector-Trailer, Access-Bytes)
    struct.pack_into("<I", buf, 0x36, 0x690F0F0F)
    for i in range(1, 0x10):
        struct.pack_into("<I", buf, i * 0x40 + 0x36, 0x69080F7F)
    # Figur-Infos
    struct.pack_into("<H", buf, 0x00, ((sky_id | sky_var) + 1) & 0xFFFF)
    struct.pack_into("<H", buf, 0x10, sky_id)
    struct.pack_into("<H", buf, 0x1C, sky_var)
    # Checksumme ueber die ersten 0x1E Bytes
    struct.pack_into("<H", buf, 0x1E, crc16(buf[:0x1E]))
    return bytes(buf)


def parse_sky(path):
    """Liest (id, variante) aus einer .sky/.bin/.dmp/.dump-Datei, wie RPCS3 beim Laden."""
    try:
        with open(path, "rb") as f:
            data = f.read(0x20)
        if len(data) < 0x20:
            return None
        sky_id = struct.unpack_from("<H", data, 0x10)[0]
        sky_var = struct.unpack_from("<H", data, 0x1C)[0]
        return sky_id, sky_var
    except OSError:
        return None

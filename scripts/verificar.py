#!/usr/bin/env python3
"""Comprueba recursos, enlaces y patrones comunes de datos sensibles sin red."""

import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()


class ReadmeLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and name in {'href', 'src'}:
                self.links.append(value)
            elif value and name == 'srcset':
                self.links.extend(candidate.strip().split()[0] for candidate in value.split(',') if candidate.strip())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def png_rgba(path):
    data = path.read_bytes()
    require(data[:8] == b'\x89PNG\r\n\x1a\n', 'Firma PNG incorrecta.')
    offset, packed, header = 8, bytearray(), None
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == crc, 'CRC PNG incorrecto.')
        if kind == b'IHDR':
            header = struct.unpack('>IIBBBBB', payload)
        elif kind == b'IDAT':
            packed.extend(payload)
        elif kind == b'IEND':
            break
        offset += 12 + length
    require(header is not None, 'Falta la cabecera PNG.')
    width, height, depth, color, compression, filtering, interlace = header
    require((width, height, depth, color, compression, filtering, interlace) ==
            (1536, 2288, 8, 6, 0, 0, 0), 'El atlas debe ser PNG RGBA v2 de 8 bits sin entrelazado.')
    stride = width * 4
    raw = zlib.decompress(packed)
    require(len(raw) == height * (stride + 1), 'Longitud PNG inesperada.')
    prior = bytearray(stride)
    pixels = bytearray()
    for y in range(height):
        start = y * (stride + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        require(method in range(5), 'Filtro PNG desconocido.')
        for x in range(stride):
            left = row[x - 4] if x >= 4 else 0
            above = prior[x]
            diagonal = prior[x - 4] if x >= 4 else 0
            if method == 1:
                predictor = left
            elif method == 2:
                predictor = above
            elif method == 3:
                predictor = (left + above) // 2
            elif method == 4:
                p = left + above - diagonal
                distances = [abs(p - left), abs(p - above), abs(p - diagonal)]
                predictor = [left, above, diagonal][distances.index(min(distances))]
            else:
                predictor = 0
            row[x] = (row[x] + predictor) & 255
        pixels.extend(row)
        prior = row
    return pixels


def verify():
    checksums = json.loads((ROOT / 'recursos/sha256.json').read_text())
    for name, expected in checksums.items():
        path = ROOT / name
        require(path.resolve().is_relative_to(ROOT), 'Ruta fuera del repositorio.')
        require(path.is_file() and not path.is_symlink(), f'Recurso ausente o enlace simbólico: {name}')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                f'La suma SHA-256 no coincide: {name}')

    pixels = png_rgba(ROOT / 'recursos/spritesheet.png')
    counts = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
    for row, count in enumerate(counts):
        for col in range(8):
            visible = 0
            for y in range(row * 208, (row + 1) * 208):
                offset = (y * 1536 + col * 192) * 4
                visible += sum(alpha > 0 for alpha in pixels[offset + 3:offset + 192 * 4:4])
            require(visible > 0 if col < count else visible == 0,
                    f'Ocupación incorrecta en fila {row}, columna {col}.')
    spec = json.loads((ROOT / 'recursos/especificacion.json').read_text())
    require(spec['fotogramas_por_fila'] == counts, 'La especificación no coincide con el atlas.')

    readme = (ROOT / 'README.md').read_text()
    html_links = ReadmeLinks()
    html_links.feed(readme)
    for link in re.findall(r'\]\(([^)]+)\)', readme) + html_links.links:
        if link.startswith('#'):
            continue
        require(not re.match(r'[a-z]+:', link), 'El README debe usar enlaces locales.')
        target = (ROOT / link.split('#')[0]).resolve()
        require(target.is_relative_to(ROOT) and target.exists(), f'Enlace local roto: {link}')

    patterns = [
        rb'/Users/[^/\s]+/', rb'/home/[^/\s]+/',
        rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        rb'gh[pousr]_[A-Za-z0-9]{20,}', rb'github_pat_[A-Za-z0-9_]{20,}',
        rb'AKIA[0-9A-Z]{16}', rb'sk-[A-Za-z0-9_-]{20,}',
        rb'pet_[a-f0-9]{24,}', rb'file_[a-f0-9]{24,}',
        rb'oaiusercontent\.com', rb'upload_session_id',
    ]
    files = [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts]
    for path in files:
        require(not path.is_symlink(), f'Enlace simbólico no permitido: {path.relative_to(ROOT)}')
        name = path.name.lower()
        require(not name.startswith('.env') and path.suffix.lower() not in {'.pem', '.key', '.p12', '.pfx'},
                f'Archivo sensible no permitido: {path.relative_to(ROOT)}')
        if path.resolve() == SELF:
            continue  # Las expresiones del verificador describen estos patrones.
        content = path.read_bytes()
        for pattern in patterns:
            require(re.search(pattern, content) is None,
                    f'Patrón sensible detectado en {path.relative_to(ROOT)}; contenido omitido.')
    print(f'Integridad: {len(checksums)} recursos correctos.')
    print('Atlas: 9 animaciones, 16 miradas, 73 fotogramas y 15 celdas vacías correctos.')
    print('Enlaces locales y revisión acotada de datos sensibles: correctos.')


if __name__ == '__main__':
    try:
        verify()
    except (ValueError, OSError, KeyError, zlib.error, struct.error) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)

"""IPP attribute wire codec for local simulated printers (RFC 8010 subset)."""
from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Any

VERSION = b'\x02\x00'
CHARSET, LANGUAGE, KEYWORD, URI, TEXT, NAME, MIMETYPE = 0x47, 0x48, 0x44, 0x45, 0x41, 0x42, 0x49
INTEGER, ENUM, BOOLEAN, RESOLUTION = 0x21, 0x23, 0x22, 0x32

@dataclass
class Request:
    version: bytes
    operation: int
    request_id: int
    attributes: dict[str, list[Any]]
    document: bytes

    def first(self, name: str, default=None):
        values = self.attributes.get(name)
        return values[0] if values else default

def decode_value(tag: int, value: bytes) -> Any:
    if tag in (INTEGER, ENUM) and len(value) == 4:
        return struct.unpack('!i', value)[0]
    if tag == BOOLEAN and len(value) == 1:
        return bool(value[0])
    if tag == RESOLUTION and len(value) == 9:
        return struct.unpack('!iiB', value)
    if tag in (CHARSET, LANGUAGE, KEYWORD, URI, TEXT, NAME, MIMETYPE, 0x4A):
        return value.decode('utf-8', 'replace')
    return value

def parse_request(payload: bytes) -> Request:
    if len(payload) < 9:
        raise ValueError('IPP request too short')
    version, operation, request_id = payload[:2], *struct.unpack('!HI', payload[2:8])
    attrs: dict[str, list[Any]] = {}
    position = 8
    current_name = ''
    collection_name = ''
    member_name = ''
    while position < len(payload):
        tag = payload[position]
        position += 1
        if tag == 3:
            return Request(version, operation, request_id, attrs, payload[position:])
        if tag in (1, 2, 4, 5):
            current_name = ''
            collection_name = ''
            member_name = ''
            continue
        if position + 4 > len(payload):
            raise ValueError('Truncated IPP attribute lengths')
        nlen = struct.unpack_from('!H', payload, position)[0]
        position += 2
        if position + nlen + 2 > len(payload):
            raise ValueError('Truncated IPP attribute name')
        name = payload[position:position+nlen].decode('utf-8', 'replace')
        position += nlen
        vlen = struct.unpack_from('!H', payload, position)[0]
        position += 2
        if position + vlen > len(payload):
            raise ValueError('Truncated IPP attribute value')
        raw = payload[position:position+vlen]
        position += vlen
        if name:
            current_name = name
        if tag == 0x34:
            collection_name = current_name
            member_name = ''
            continue
        if tag == 0x37:
            collection_name = ''
            member_name = ''
            continue
        if tag == 0x4A:
            member_name = decode_value(tag, raw)
            continue
        key = member_name if collection_name and member_name else current_name
        if key:
            attrs.setdefault(key, []).append(decode_value(tag, raw))
    raise ValueError('IPP end-of-attributes delimiter missing')

def attr(tag: int, name: str, values: Any) -> bytes:
    if not isinstance(values, list):
        values = [values]
    out = bytearray()
    for index, value in enumerate(values):
        name_bytes = name.encode('utf-8') if index == 0 else b''
        if tag in (INTEGER, ENUM):
            raw = struct.pack('!i', int(value))
        elif tag == BOOLEAN:
            raw = b'\x01' if value else b'\x00'
        elif tag == RESOLUTION:
            raw = struct.pack('!iiB', *value)
        elif isinstance(value, bytes):
            raw = value
        else:
            raw = str(value).encode('utf-8')
        out.extend(bytes([tag]) + struct.pack('!H', len(name_bytes)) + name_bytes
                   + struct.pack('!H', len(raw)) + raw)
    return bytes(out)

def response(request: Request, status: int, printer_attrs=(), job_attrs=()) -> bytes:
    out = bytearray((request.version if request.version in (b'\x01\x01', b'\x02\x00', b'\x02\x01') else VERSION))
    out.extend(struct.pack('!HI', status, request.request_id))
    out.extend(b'\x01')
    out.extend(attr(CHARSET, 'attributes-charset', 'utf-8'))
    out.extend(attr(LANGUAGE, 'attributes-natural-language', 'en-us'))
    if printer_attrs:
        out.extend(b'\x04')
        for tag, name, val in printer_attrs:
            out.extend(attr(tag, name, val))
    if job_attrs:
        out.extend(b'\x02')
        for tag, name, val in job_attrs:
            out.extend(attr(tag, name, val))
    out.extend(b'\x03')
    return bytes(out)

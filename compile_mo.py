#!/usr/bin/env python3
"""Compile .po files to .mo binary format (pure Python, no gettext needed)."""
import struct
import sys
from pathlib import Path


def unescape(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
    return s


def parse_po(path):
    """Parse a .po file and return a dict of {msgid: msgstr}."""
    catalog = {}
    msgid = None
    msgstr = None
    in_msgid = False
    in_msgstr = False

    def flush():
        nonlocal msgid, msgstr, in_msgid, in_msgstr
        if msgid is not None and msgstr is not None:
            if msgid not in catalog:
                catalog[msgid] = msgstr
        msgid = None
        msgstr = None
        in_msgid = False
        in_msgstr = False

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            if not line or line.startswith('#'):
                flush()
                continue

            if line.startswith('msgid '):
                flush()
                msgid = unescape(line[6:])
                in_msgid = True
                in_msgstr = False

            elif line.startswith('msgstr '):
                msgstr = unescape(line[7:])
                in_msgid = False
                in_msgstr = True

            elif line.startswith('"'):
                chunk = unescape(line)
                if in_msgid and msgid is not None:
                    msgid += chunk
                elif in_msgstr and msgstr is not None:
                    msgstr += chunk

    flush()
    return catalog


def build_mo(catalog):
    """Build binary .mo data from {msgid: msgstr} dict."""
    # Ensure a proper header with charset=UTF-8 is present
    if '' not in catalog or 'charset=UTF-8' not in catalog.get('', ''):
        catalog[''] = (
            'Content-Type: text/plain; charset=UTF-8\n'
            'Content-Transfer-Encoding: 8bit\n'
        )

    # Sort by msgid bytes (empty string sorts first, which is required)
    keys = sorted(catalog.keys())
    N = len(keys)

    # Header: 7 × uint32 = 28 bytes
    # Orig table:  N × 2 × uint32 = N × 8 bytes
    # Trans table: N × 2 × uint32 = N × 8 bytes
    strings_start = 28 + N * 16

    orig_encoded = [k.encode('utf-8') for k in keys]
    trans_encoded = [catalog[k].encode('utf-8') for k in keys]

    orig_table = []
    orig_block = b''
    for s in orig_encoded:
        orig_table.append((len(s), strings_start + len(orig_block)))
        orig_block += s + b'\x00'

    trans_start = strings_start + len(orig_block)
    trans_table = []
    trans_block = b''
    for s in trans_encoded:
        trans_table.append((len(s), trans_start + len(trans_block)))
        trans_block += s + b'\x00'

    magic = 0x950412de
    revision = 0
    orig_offset = 28
    trans_offset = 28 + N * 8
    hash_size = 0
    hash_offset = 28 + N * 16

    header = struct.pack('<7I', magic, revision, N,
                         orig_offset, trans_offset,
                         hash_size, hash_offset)

    orig_tbl = b''.join(struct.pack('<2I', l, o) for l, o in orig_table)
    trans_tbl = b''.join(struct.pack('<2I', l, o) for l, o in trans_table)

    return header + orig_tbl + trans_tbl + orig_block + trans_block


def compile_po(po_path):
    po_path = Path(po_path)
    mo_path = po_path.with_suffix('.mo')
    catalog = parse_po(po_path)
    mo_data = build_mo(catalog)
    with open(mo_path, 'wb') as f:
        f.write(mo_data)
    print(f'Compiled: {po_path} → {mo_path} ({len(catalog)} entries)')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        base = Path(__file__).parent / 'feeds' / 'locale'
        po_files = list(base.rglob('*.po'))
        if not po_files:
            print('No .po files found.')
            sys.exit(1)
        for po in po_files:
            compile_po(po)
    else:
        for arg in sys.argv[1:]:
            compile_po(arg)

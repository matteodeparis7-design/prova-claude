#!/usr/bin/env python3
"""Genera index.html (sito pronto da pubblicare) partendo da src/galo-studios.html."""
from pathlib import Path
here = Path(__file__).resolve().parent
src = (here / 'src' / 'galo-studios.html').read_text(encoding='utf-8')
cut = src.index('</style>') + len('</style>')
head, body = src[:cut], src[cut:]
page = (
    '<!DOCTYPE html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
    'img{max-width:100%}[hidden]{display:none!important}</style>\n'
    + head + '\n</head>\n<body>' + body + '\n</body>\n</html>\n'
)
(here / 'index.html').write_text(page, encoding='utf-8')
print('index.html scritto,', len(page.encode()), 'byte')

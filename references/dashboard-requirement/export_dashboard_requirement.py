#!/usr/bin/python3
import os
import sys
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    item = PropertyValue()
    item.Name = name
    item.Value = value
    return item


source = Path('/home/ubuntu/build_dashboard_requirement_short.html').resolve()
output_dir = Path('/tmp/dashboard_requirement').resolve()
output_dir.mkdir(parents=True, exist_ok=True)
docx_output = output_dir / '新一代数智财务运营管控平台全周期领导驾驶舱展示需求（精简稿）.docx'
pdf_output = output_dir / '新一代数智财务运营管控平台全周期领导驾驶舱展示需求（精简稿）.pdf'

local_ctx = uno.getComponentContext()
resolver = local_ctx.ServiceManager.createInstanceWithContext(
    'com.sun.star.bridge.UnoUrlResolver', local_ctx
)
ctx = None
for _ in range(60):
    try:
        ctx = resolver.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext')
        break
    except Exception:
        time.sleep(0.5)
if ctx is None:
    raise RuntimeError('Unable to connect to LibreOffice Writer')

desktop = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
document = desktop.loadComponentFromURL(
    uno.systemPathToFileUrl(str(source)), '_blank', 0,
    (prop('Hidden', True), prop('FilterName', 'HTML (StarWriter)')),
)
if document is None:
    raise RuntimeError('Unable to load source document')

document.storeToURL(
    uno.systemPathToFileUrl(str(docx_output)),
    (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)),
)
document.storeToURL(
    uno.systemPathToFileUrl(str(pdf_output)),
    (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)),
)
document.close(True)
print(docx_output)
print(pdf_output)

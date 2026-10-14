"""Generated synthetic sources only; no vehicle procedures or private manuals."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_bytes(kinds=("text",), encrypted=False):
    writer = PdfWriter()
    for number, kind in enumerate(kinds, 1):
        page = writer.add_blank_page(width=300, height=300)
        if kind == "text":
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(
                f"BT /F1 12 Tf 10 250 Td (SYNTHETIC training page {number}. Not repair evidence.) Tj ET".encode()
            )
            page[NameObject("/Contents")] = writer._add_object(stream)
        else:
            # Actual image XObject, not an empty-page surrogate for a scan.
            from pypdf.generic import NumberObject

            image = DecodedStreamObject()
            image.set_data(bytes([255, 255, 255, 0, 0, 0, 0, 0, 0, 255, 255, 255]))
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(2),
                    NameObject("/Height"): NumberObject(2),
                    NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject("/Im1"): writer._add_object(image)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(b"q 200 0 0 200 10 10 cm /Im1 Do Q")
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-fixture-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def metadata(**overrides):
    return dict(
        title="合成资料 / synthetic",
        source_kind="synthetic_fixture",
        source_reference="generated locally, not a vehicle manual",
        source_status="unknown",
        license_status="unknown",
        scope={"model": "合成车型"},
        synthetic=True,
        **overrides,
    )


MARKDOWN = (
    "# 合成资料\n\n前置条件：仅验证软件，不是维修指导。\n\n## 演示步骤\n\n操作前请确认测试环境。\n\n1. Unicode 中文🙂\n2. 保留原文定位\n\n| 项目 | 合成值 |\n| --- | --- |\n"
    + "".join(f"| row{i} | synthetic value {i} 中文 |\n" for i in range(180))
    + "\n## 长段落\n\n"
    + ("中文🙂合法 Unicode long paragraph " * 900)
    + "\n\n<script>alert('synthetic')</script>\n[external](https://example.invalid/never-fetch)\n"
)

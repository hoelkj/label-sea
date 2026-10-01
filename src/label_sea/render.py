from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from label_sea.models import Component

MM_TO_PT = 72 / 25.4

TYPE_COLORS = {
    "generator": {"accent": "#2E7D32", "fill": "#EFF8F0"},
    "consumer": {"accent": "#B26A00", "fill": "#FFF8EB"},
    "distributor": {"accent": "#005B96", "fill": "#EEF6FC"},
}


def preferred_font_family() -> str:
    candidates = [
        "Lubalin Graph",
        "Lubalin",
        "ITC Lubalin Graph Std",
        "Arial",
        "DejaVu Sans",
        "Noto Sans",
    ]
    formatted = ", ".join(f'"{candidate}"' for candidate in candidates)
    return f"{formatted}, sans-serif"


def _find_font_file() -> str | None:
    custom_font_dir = os.environ.get("LABEL_SEA_FONT")
    roots = [Path(custom_font_dir)] if custom_font_dir else []
    project_root = Path(__file__).resolve().parents[2]
    roots.extend(
        [
            project_root / "fonts",
            Path.cwd() / "fonts",
            Path.home() / ".fonts",
            Path.home() / ".local" / "share" / "fonts",
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
        ]
    )

    patterns = ["*Lubalin*", "*LubalinGraph*", "*lubalin*"]
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for match in glob.glob(str(root / pattern), recursive=True):
                normalized = str(Path(match))
                if normalized in seen:
                    continue
                seen.add(normalized)
                if match.lower().endswith((".ttf", ".otf", ".ttc")):
                    return normalized
    return None


def _register_lubalin_font_if_present() -> str | None:
    font_file = _find_font_file()
    if not font_file:
        return None
    font_name = "Lubalin"
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_file))
    except Exception:
        return None
    return font_name


LUBALIN_FONT = _register_lubalin_font_if_present()


def pdf_font_name(is_bold: bool) -> str:
    if LUBALIN_FONT is not None:
        return LUBALIN_FONT
    return "Helvetica-Bold" if is_bold else "Helvetica"


@dataclass(slots=True)
class PortLayout:
    x_mm: float
    text_x_mm: float
    text_y_mm: float
    side: str
    label: str
    style: str
    tag: str | None = None


@dataclass(slots=True)
class LabelLayout:
    component: Component
    width_mm: float
    height_mm: float
    title_y_mm: float
    meta_y_mm: float
    title_size_mm: float
    meta_size_mm: float
    title_text: str
    meta_text: str
    top_ports: list[PortLayout]
    bottom_ports: list[PortLayout]


@dataclass(slots=True)
class PdfPagePlan:
    page_size: tuple[float, float]
    paper_format: str
    orientation: str
    warning: str | None = None


def render_component_svg(
    component: Component,
    band_height_mm: int,
    output_path: Path,
) -> LabelLayout:
    layout = build_layout(component, band_height_mm)
    svg = build_svg_tree(layout)
    ET.indent(svg)
    output_path.write_text(ET.tostring(svg, encoding="unicode"), encoding="utf-8")
    return layout


def render_pdf(layouts: list[LabelLayout], page_format: str, output_path: Path) -> PdfPagePlan:
    plan = choose_pdf_page_plan(layouts, page_format)
    page_size = plan.page_size
    pdf = canvas.Canvas(str(output_path), pagesize=page_size)
    margin_pt = 14 * MM_TO_PT
    gap_pt = 6 * MM_TO_PT

    page_width_pt, page_height_pt = page_size
    cursor_x = margin_pt
    cursor_y = page_height_pt - margin_pt
    row_height = 0.0

    for layout in layouts:
        width_pt = layout.width_mm * MM_TO_PT
        height_pt = layout.height_mm * MM_TO_PT

        if cursor_x + width_pt > page_width_pt - margin_pt:
            cursor_x = margin_pt
            cursor_y -= row_height + gap_pt
            row_height = 0.0

        if cursor_y - height_pt < margin_pt:
            pdf.showPage()
            cursor_x = margin_pt
            cursor_y = page_height_pt - margin_pt
            row_height = 0.0

        draw_pdf_label(pdf, layout, cursor_x, cursor_y - height_pt)
        cursor_x += width_pt + gap_pt
        row_height = max(row_height, height_pt)

    pdf.save()
    return plan


def build_layout(component: Component, band_height_mm: int) -> LabelLayout:
    top_ports = component.inputs
    bottom_ports = component.outputs
    columns = max(len(top_ports), len(bottom_ports), 1)
    height_mm = float(band_height_mm)
    title_y_mm, meta_y_mm = text_profile(component.type, height_mm)
    meta_text = component.type_label
    if component.power_label:
        meta_text = f"{meta_text} | {component.power_label}"
    title_text = compact_text(component.name, 34)

    title_size_mm = fit_font_size(title_text, 7.8, 6.2)
    meta_size_mm = fit_font_size(meta_text, 4.8, 3.6)
    width_mm = compute_label_width_mm(
        component,
        columns,
        title_text,
        meta_text,
        title_size_mm,
        meta_size_mm,
    )
    return LabelLayout(
        component=component,
        width_mm=width_mm,
        height_mm=height_mm,
        title_y_mm=title_y_mm,
        meta_y_mm=meta_y_mm,
        title_size_mm=title_size_mm,
        meta_size_mm=meta_size_mm,
        title_text=title_text,
        meta_text=meta_text,
        top_ports=port_layouts(top_ports, width_mm, height_mm, "top"),
        bottom_ports=port_layouts(bottom_ports, width_mm, height_mm, "bottom"),
    )


def text_profile(component_type: str, height_mm: float) -> tuple[float, float]:
    if component_type == "generator":
        return 17.0, 24.0
    if component_type == "consumer":
        return height_mm - 17.0, height_mm - 10.0
    return (height_mm / 2) - 1.5, (height_mm / 2) + 5.5


def port_layouts(ports: list, width_mm: float, height_mm: float, side: str) -> list[PortLayout]:
    if not ports:
        return []

    margin_mm = 6.0
    if len(ports) == 1:
        positions = [width_mm / 2]
    else:
        usable_width = width_mm - 2 * margin_mm
        step = usable_width / (len(ports) - 1)
        positions = [margin_mm + index * step for index in range(len(ports))]

    text_y = 11.0 if side == "top" else height_mm - 11.0
    offset = -3.4 if side == "top" else 3.4
    return [
        PortLayout(
            x_mm=position,
            text_x_mm=position + offset,
            text_y_mm=text_y,
            side=side,
            label=port.short_name,
            style=port.style,
            tag=port_tag(port.style),
        )
        for position, port in zip(positions, ports, strict=True)
    ]


def compute_label_width_mm(
    component: Component,
    columns: int,
    title_text: str,
    meta_text: str,
    title_size_mm: float,
    meta_size_mm: float,
) -> float:
    port_count_width = 20.0 + columns * 12.0
    title_width = 22.0 + estimated_text_width_mm(title_text, title_size_mm)
    meta_width = 22.0 + estimated_text_width_mm(meta_text, meta_size_mm)
    port_label_width = 40.0 + max_port_label_length(component) * 1.6
    return max(110.0, port_count_width, title_width, meta_width, port_label_width)


def choose_pdf_page_plan(layouts: list[LabelLayout], page_format: str) -> PdfPagePlan:
    if page_format == "a4":
        candidates = [
            PdfPagePlan(page_size=A4, paper_format="a4", orientation="portrait"),
            PdfPagePlan(page_size=landscape(A4), paper_format="a4", orientation="landscape"),
            PdfPagePlan(
                page_size=landscape(A3),
                paper_format="a3",
                orientation="landscape",
                warning="Requested A4 PDF was too narrow; using A3 landscape instead.",
            ),
        ]
    else:
        candidates = [
            PdfPagePlan(page_size=A3, paper_format="a3", orientation="portrait"),
            PdfPagePlan(page_size=landscape(A3), paper_format="a3", orientation="landscape"),
        ]

    if not layouts:
        return candidates[0]

    required_width_pt = max(layout.width_mm * MM_TO_PT for layout in layouts) + (2 * 14 * MM_TO_PT)
    for candidate in candidates:
        if required_width_pt <= candidate.page_size[0]:
            return candidate

    overflow_warning = (
        f"Requested {page_format.upper()} PDF is too narrow even on A3 landscape; "
        "some labels may be clipped."
    )
    return PdfPagePlan(
        page_size=landscape(A3),
        paper_format="a3",
        orientation="landscape",
        warning=overflow_warning,
    )


def choose_pdf_page_size(layouts: list[LabelLayout], page_format: str) -> tuple[float, float]:
    return choose_pdf_page_plan(layouts, page_format).page_size


def max_port_label_length(component: Component) -> int:
    labels = [port.short_name for port in [*component.inputs, *component.outputs]]
    if not labels:
        return 0
    return max(len(label) for label in labels)


def estimated_text_width_mm(text: str, font_size_mm: float) -> float:
    return len(text) * font_size_mm * 0.38


def fit_font_size(text: str, base_size_mm: float, min_size_mm: float) -> float:
    if len(text) <= 18:
        return base_size_mm
    overflow = min(len(text) - 18, 18)
    shrink = overflow * 0.08
    return max(min_size_mm, base_size_mm - shrink)


def compact_text(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 1].rstrip()}…"


def build_svg_tree(layout: LabelLayout) -> ET.Element:
    colors = TYPE_COLORS[layout.component.type]
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{layout.width_mm}mm",
            "height": f"{layout.height_mm}mm",
            "viewBox": f"0 0 {layout.width_mm} {layout.height_mm}",
        },
    )

    ET.SubElement(
        root,
        "rect",
        {
            "x": "0.8",
            "y": "0.8",
            "width": f"{layout.width_mm - 1.6}",
            "height": f"{layout.height_mm - 1.6}",
            "rx": "3",
            "fill": colors["fill"],
            "stroke": "none",
        },
    )
    ET.SubElement(
        root,
        "line",
        {
            "x1": "1.0",
            "y1": "3.0",
            "x2": "1.0",
            "y2": f"{layout.height_mm - 3.0}",
            "stroke": colors["accent"],
            "stroke-width": "1.8",
            "stroke-linecap": "round",
        },
    )
    ET.SubElement(
        root,
        "line",
        {
            "x1": f"{layout.width_mm - 1.0}",
            "y1": "3.0",
            "x2": f"{layout.width_mm - 1.0}",
            "y2": f"{layout.height_mm - 3.0}",
            "stroke": colors["accent"],
            "stroke-width": "1.8",
            "stroke-linecap": "round",
        },
    )

    add_text(
        root,
        layout.width_mm / 2,
        layout.title_y_mm,
        layout.title_text,
        layout.title_size_mm,
        "#132029",
        "middle",
        600,
    )
    add_text(
        root,
        layout.width_mm / 2,
        layout.meta_y_mm,
        layout.meta_text,
        layout.meta_size_mm,
        "#27404C",
        "middle",
        400,
    )

    for port in layout.top_ports:
        add_port_svg(root, layout.height_mm, port, colors["accent"])
    for port in layout.bottom_ports:
        add_port_svg(root, layout.height_mm, port, colors["accent"])

    return root


def add_port_svg(root: ET.Element, height_mm: float, port: PortLayout, color: str) -> None:
    if port.side == "top":
        line_start = 10.0
        line_end = 0.0
    else:
        line_start = height_mm - 10.0
        line_end = height_mm

    line_attributes = {
        "x1": f"{port.x_mm}",
        "y1": f"{line_start}",
        "x2": f"{port.x_mm}",
        "y2": f"{line_end}",
        "stroke": color,
        "stroke-width": "1.2",
    }
    dasharray = dash_pattern(port.style)
    if dasharray is not None:
        line_attributes["stroke-dasharray"] = dasharray
        line_attributes["stroke-linecap"] = "round"

    ET.SubElement(root, "line", line_attributes)
    label_text, value_text = split_port_label(port.label)
    label_font_size = "3.8"
    value_font_size = "8.0" if value_text == "Schuko" else "7.0"
    label_y = port.text_y_mm - 1.6
    value_y = port.text_y_mm + 2.2
    if label_text:
        text = ET.SubElement(
            root,
            "text",
            {
                "x": f"{port.text_x_mm}",
                "y": f"{label_y}",
                "font-size": label_font_size,
                "font-family": preferred_font_family(),
                "font-weight": "500",
                "fill": color,
                "text-anchor": "middle",
                "transform": f"rotate(-90 {port.text_x_mm} {label_y})",
            },
        )
        text.text = label_text

    value = ET.SubElement(
        root,
        "text",
        {
            "x": f"{port.text_x_mm}",
            "y": f"{value_y}",
            "font-size": value_font_size,
            "font-family": preferred_font_family(),
            "font-weight": "700",
            "fill": color,
            "text-anchor": "middle",
            "transform": f"rotate(-90 {port.text_x_mm} {value_y})",
        },
    )
    value.text = value_text

    if port.tag:
        offset = 2.0
        tag_x = port.x_mm - (port.text_x_mm - port.x_mm) + offset
        tag = ET.SubElement(
            root,
            "text",
            {
                "x": f"{tag_x}",
                "y": f"{port.text_y_mm}",
                "font-size": "3.0",
                "font-family": preferred_font_family(),
                "fill": color,
                "text-anchor": "middle",
                "transform": f"rotate(-90 {tag_x} {port.text_y_mm})",
            },
        )
        tag.text = port.tag


def add_text(
    root: ET.Element,
    x_mm: float,
    y_mm: float,
    content: str,
    size_mm: float,
    color: str,
    anchor: str,
    weight: int,
) -> None:
    text = ET.SubElement(
        root,
        "text",
        {
            "x": f"{x_mm}",
            "y": f"{y_mm}",
            "font-size": f"{size_mm}",
            "font-family": preferred_font_family(),
            "font-weight": str(weight),
            "fill": color,
            "text-anchor": anchor,
        },
    )
    text.text = content


def draw_pdf_label(pdf: canvas.Canvas, layout: LabelLayout, x_pt: float, y_pt: float) -> None:
    colors = TYPE_COLORS[layout.component.type]
    width_pt = layout.width_mm * MM_TO_PT
    height_pt = layout.height_mm * MM_TO_PT
    accent = HexColor(colors["accent"])
    fill = HexColor(colors["fill"])

    pdf.setFillColor(fill)
    pdf.setStrokeColor(fill)
    pdf.setLineWidth(0)
    pdf.roundRect(x_pt, y_pt, width_pt, height_pt, 8, stroke=0, fill=1)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1.8)
    pdf.line(
        x_pt + 1.0 * MM_TO_PT,
        y_pt + 3.0 * MM_TO_PT,
        x_pt + 1.0 * MM_TO_PT,
        y_pt + height_pt - 3.0 * MM_TO_PT,
    )
    pdf.line(
        x_pt + width_pt - 1.0 * MM_TO_PT,
        y_pt + 3.0 * MM_TO_PT,
        x_pt + width_pt - 1.0 * MM_TO_PT,
        y_pt + height_pt - 3.0 * MM_TO_PT,
    )

    pdf.setFillColor(HexColor("#132029"))
    pdf.setFont(pdf_font_name(True), max(7.5, layout.title_size_mm * 1.45))
    pdf.drawCentredString(
        x_pt + width_pt / 2,
        y_pt + height_pt - layout.title_y_mm * MM_TO_PT,
        layout.title_text,
    )

    pdf.setFillColor(HexColor("#27404C"))
    pdf.setFont(pdf_font_name(False), max(5.0, layout.meta_size_mm * 1.6))
    pdf.drawCentredString(
        x_pt + width_pt / 2,
        y_pt + height_pt - layout.meta_y_mm * MM_TO_PT,
        layout.meta_text,
    )

    for port in layout.top_ports:
        draw_pdf_port(pdf, layout.height_mm, x_pt, y_pt, port, accent)
    for port in layout.bottom_ports:
        draw_pdf_port(pdf, layout.height_mm, x_pt, y_pt, port, accent)


def draw_pdf_port(
    pdf: canvas.Canvas,
    height_mm: float,
    x_pt: float,
    y_pt: float,
    port: PortLayout,
    color: HexColor,
) -> None:
    port_x = x_pt + port.x_mm * MM_TO_PT
    if port.side == "top":
        line_start_y = y_pt + height_mm * MM_TO_PT - 10 * MM_TO_PT
        line_end_y = y_pt + height_mm * MM_TO_PT
        text_x = x_pt + port.text_x_mm * MM_TO_PT
        text_y = y_pt + height_mm * MM_TO_PT - 11 * MM_TO_PT
    else:
        line_start_y = y_pt + 10 * MM_TO_PT
        line_end_y = y_pt
        text_x = x_pt + port.text_x_mm * MM_TO_PT
        text_y = y_pt + 11 * MM_TO_PT

    pdf.setStrokeColor(color)
    pdf.setLineWidth(1)
    dash = pdf_dash_pattern(port.style)
    if dash is not None:
        pdf.setDash(*dash)
    pdf.line(port_x, line_start_y, port_x, line_end_y)
    if dash is not None:
        pdf.setDash()

    label_text, value_text = split_port_label(port.label)
    value_font_size = 8.3 if value_text == "Schuko" else 7.3
    label_y = text_y - 3.2 * MM_TO_PT
    value_y = text_y + 3.1 * MM_TO_PT
    if label_text:
        pdf.saveState()
        pdf.setFillColor(color)
        pdf.setFont(pdf_font_name(False), 3.9)
        pdf.translate(text_x, label_y)
        pdf.rotate(90)
        pdf.drawCentredString(0, 0, label_text)
        pdf.restoreState()

    pdf.saveState()
    pdf.setFillColor(color)
    pdf.setFont(pdf_font_name(True), value_font_size)
    pdf.translate(text_x, value_y)
    pdf.rotate(90)
    pdf.drawCentredString(0, 0, value_text)
    pdf.restoreState()

    if port.tag:
        offset_mm = 2.0
        tag_x = x_pt + (port.x_mm - (port.text_x_mm - port.x_mm) + offset_mm) * MM_TO_PT
        pdf.saveState()
        pdf.setFillColor(color)
        pdf.setFont(pdf_font_name(False), 4.8)
        pdf.translate(tag_x, text_y)
        pdf.rotate(90)
        pdf.drawCentredString(0, 0, port.tag)
        pdf.restoreState()


def dash_pattern(style: str) -> str | None:
    if style == "dashed":
        return "4,2"
    if style == "fine-dashed":
        return "2,2"
    return None


def pdf_dash_pattern(style: str) -> tuple[float, float] | None:
    if style == "dashed":
        return 4.0, 2.0
    if style == "fine-dashed":
        return 1.5, 1.5
    return None


def split_port_label(label: str) -> tuple[str, str]:
    if label == "Schuko":
        return "", "Schuko"
    if " " not in label:
        return label, label
    label_prefix, value = label.rsplit(" ", 1)
    return label_prefix, value


def port_tag(style: str) -> str | None:
    if style == "fine-dashed":
        return "Laie"
    return None

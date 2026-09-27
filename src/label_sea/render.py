from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, A4
from reportlab.pdfgen import canvas

from label_sea.models import Component

MM_TO_PT = 72 / 25.4

TYPE_COLORS = {
    "generator": {"accent": "#2E7D32", "fill": "#EFF8F0"},
    "consumer": {"accent": "#B26A00", "fill": "#FFF8EB"},
    "distributor": {"accent": "#005B96", "fill": "#EEF6FC"},
}


@dataclass(slots=True)
class PortLayout:
    x_mm: float
    text_x_mm: float
    text_y_mm: float
    side: str
    label: str


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


def render_pdf(layouts: list[LabelLayout], page_format: str, output_path: Path) -> None:
    page_size = {"a4": A4, "a3": A3}[page_format]
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

    title_size_mm = fit_font_size(title_text, 6.8, 5.4)
    meta_size_mm = fit_font_size(meta_text, 3.3, 2.7)
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

    margin_mm = 12.0
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
    port_count_width = 30.0 + columns * 22.0
    title_width = 22.0 + estimated_text_width_mm(title_text, title_size_mm)
    meta_width = 22.0 + estimated_text_width_mm(meta_text, meta_size_mm)
    port_label_width = 52.0 + max_port_label_length(component) * 2.2
    return max(70.0, port_count_width, title_width, meta_width, port_label_width)


def max_port_label_length(component: Component) -> int:
    labels = [port.short_name for port in [*component.inputs, *component.outputs]]
    if not labels:
        return 0
    return max(len(label) for label in labels)


def estimated_text_width_mm(text: str, font_size_mm: float) -> float:
    return len(text) * font_size_mm * 0.56


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

    ET.SubElement(
        root,
        "line",
        {
            "x1": f"{port.x_mm}",
            "y1": f"{line_start}",
            "x2": f"{port.x_mm}",
            "y2": f"{line_end}",
            "stroke": color,
            "stroke-width": "1.2",
        },
    )
    text = ET.SubElement(
        root,
        "text",
        {
            "x": f"{port.text_x_mm}",
            "y": f"{port.text_y_mm}",
            "font-size": "3.2",
            "font-family": "DejaVu Sans, Arial, sans-serif",
            "fill": color,
            "text-anchor": "middle",
            "transform": f"rotate(-90 {port.text_x_mm} {port.text_y_mm})",
        },
    )
    text.text = port.label


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
            "font-family": "DejaVu Sans, Arial, sans-serif",
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
    pdf.setFont("Helvetica-Bold", max(7.5, layout.title_size_mm * 1.45))
    pdf.drawCentredString(
        x_pt + width_pt / 2,
        y_pt + height_pt - layout.title_y_mm * MM_TO_PT,
        layout.title_text,
    )

    pdf.setFillColor(HexColor("#27404C"))
    pdf.setFont("Helvetica", max(5.0, layout.meta_size_mm * 1.6))
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
    pdf.line(port_x, line_start_y, port_x, line_end_y)

    pdf.saveState()
    pdf.setFillColor(color)
    pdf.setFont("Helvetica", 5.5)
    pdf.translate(text_x, text_y)
    pdf.rotate(90)
    pdf.drawCentredString(0, 0, port.label)
    pdf.restoreState()

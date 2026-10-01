from pathlib import Path

from reportlab.lib.pagesizes import A3, A4, landscape

from label_sea.models import Component, Port
from label_sea.render import (
    build_layout,
    choose_pdf_page_plan,
    choose_pdf_page_size,
    render_component_svg,
)


def test_layout_expands_for_many_ports_and_long_name() -> None:
    component = Component(
        key="long-distributor",
        name="Verteiler mit besonders langem Namen fuer die Layoutprobe",
        type="distributor",
        inputs=[Port(kind="CEE", ampere=125)],
        outputs=[
            Port(kind="CEE", ampere=63),
            Port(kind="CEE", ampere=32),
            Port(kind="CEE", ampere=16),
            Port(kind="Schuko", ampere=16),
            Port(kind="Schuko", ampere=16),
        ],
    )

    layout = build_layout(component, 50)

    assert 110 <= layout.width_mm < 135
    assert layout.title_size_mm <= 6.8
    assert layout.meta_size_mm <= 3.3


def test_wide_labels_switch_a4_to_landscape() -> None:
    component = Component(
        key="wide-generator",
        name="Breiter Erzeuger",
        type="generator",
        outputs=[Port(kind="CEE", ampere=63) for _ in range(14)],
    )

    layout = build_layout(component, 50)

    assert choose_pdf_page_size([layout], "a4") == landscape(A4)


def test_extra_wide_labels_switch_a4_to_a3_with_warning() -> None:
    component = Component(
        key="extra-wide-generator",
        name="Sehr breiter Erzeuger",
        type="generator",
        outputs=[Port(kind="CEE", ampere=63) for _ in range(24)],
    )

    layout = build_layout(component, 50)
    plan = choose_pdf_page_plan([layout], "a4")

    assert plan.page_size == landscape(A3)
    assert plan.warning == "Requested A4 PDF was too narrow; using A3 landscape instead."


def test_narrow_labels_keep_a4_portrait() -> None:
    component = Component(
        key="narrow-consumer",
        name="Pumpe",
        type="consumer",
        inputs=[Port(kind="CEE", ampere=32)],
    )

    layout = build_layout(component, 50)

    assert choose_pdf_page_size([layout], "a4") == A4


def test_rendered_svg_contains_full_edge_connector(tmp_path: Path) -> None:
    component = Component(
        key="consumer-1",
        name="Pumpe",
        type="consumer",
        inputs=[Port(kind="CEE", ampere=32)],
    )

    output_file = tmp_path / "consumer.svg"
    render_component_svg(component, 50, output_file)
    svg = output_file.read_text(encoding="utf-8")

    assert 'y2="0.0"' in svg
    assert "Schuko" not in svg


def test_rendered_svg_contains_fine_dashed_connector(tmp_path: Path) -> None:
    component = Component(
        key="generator-1",
        name="Notstromaggregat",
        type="generator",
        outputs=[Port(kind="CEE", ampere=16, style="fine-dashed")],
    )

    output_file = tmp_path / "generator.svg"
    render_component_svg(component, 50, output_file)
    svg = output_file.read_text(encoding="utf-8")

    assert 'stroke-dasharray="2,2"' in svg
    assert "CEE 16A" in svg

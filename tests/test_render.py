from pathlib import Path

from label_sea.models import Component, Port
from label_sea.render import build_layout, render_component_svg


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

    assert layout.width_mm >= 140
    assert layout.title_size_mm <= 6.8
    assert layout.meta_size_mm <= 3.3


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

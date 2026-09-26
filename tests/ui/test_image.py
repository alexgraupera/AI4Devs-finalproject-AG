"""The image ships every module the UI imports: a page that imports a file the image lacks dies on start-up."""

import pathlib
import re

ROOT = pathlib.Path(__file__).parents[2]


def test_every_ui_module_the_pages_import_is_copied_into_the_image() -> None:
    sources = [ROOT / "streamlit_app.py", *ROOT.glob("pages/*.py"), *ROOT.glob("ui_*.py")]
    imported = {
        module
        for source in sources
        for module in re.findall(r"^(?:from|import) (ui_\w+)", source.read_text(encoding="utf-8"), re.M)
    }
    copied = re.findall(r"^COPY (.+) \./$", (ROOT / "Dockerfile").read_text(encoding="utf-8"), re.M)

    assert imported, "the pages import no ui_ module: the pattern above is out of date"
    assert {f"{module}.py" for module in imported} <= {name for line in copied for name in line.split()}


def test_the_ui_theme_is_copied_into_the_image() -> None:
    # Streamlit reads it from the working directory; left out, production falls back to red focus.
    assert (ROOT / ".streamlit" / "config.toml").exists()
    assert "COPY .streamlit ./.streamlit" in (ROOT / "Dockerfile").read_text(encoding="utf-8")

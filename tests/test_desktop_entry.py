from pathlib import Path

from vars_gridview.lib.runtime import desktop_entry


def _write_iconset(iconset_dir: Path) -> None:
    iconset_dir.mkdir(parents=True, exist_ok=True)
    for size in desktop_entry.ICON_SIZES:
        (iconset_dir / f"icon_{size}.png").write_bytes(f"{size}".encode("ascii"))


def test_install_desktop_entry_linux(tmp_path, monkeypatch):
    xdg_data_home = tmp_path / "xdg-data"
    iconset_dir = tmp_path / "assets" / "icons" / "VARSGridView.iconset"
    _write_iconset(iconset_dir)

    calls = []
    monkeypatch.setattr(desktop_entry.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))
    monkeypatch.setattr(desktop_entry, "ICONSET_DIR", iconset_dir)
    monkeypatch.setattr(
        desktop_entry, "_resolve_exec_path", lambda: "/usr/bin/vars-gridview"
    )
    monkeypatch.setattr(
        desktop_entry, "_best_effort_run", lambda command: calls.append(command)
    )

    rc = desktop_entry.install_desktop_entry()

    assert rc == 0
    desktop_path = xdg_data_home / "applications" / "vars-gridview.desktop"
    assert desktop_path.exists()
    contents = desktop_path.read_text(encoding="utf-8")
    assert "Name=VARS GridView" in contents
    assert "Exec=/usr/bin/vars-gridview" in contents
    assert "Icon=vars-gridview" in contents

    for size in desktop_entry.ICON_SIZES:
        icon_path = (
            xdg_data_home
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / "vars-gridview.png"
        )
        assert icon_path.exists()
        assert icon_path.read_bytes() == f"{size}".encode("ascii")

    assert calls == [
        ["update-desktop-database", str(xdg_data_home / "applications")],
        ["gtk-update-icon-cache", "-f", "-t", str(xdg_data_home / "icons" / "hicolor")],
    ]


def test_uninstall_desktop_entry_linux(tmp_path, monkeypatch):
    xdg_data_home = tmp_path / "xdg-data"
    applications = xdg_data_home / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    (applications / "vars-gridview.desktop").write_text(
        "[Desktop Entry]\n", encoding="utf-8"
    )

    for size in desktop_entry.ICON_SIZES:
        icon_path = (
            xdg_data_home
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / "vars-gridview.png"
        )
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        icon_path.write_bytes(b"x")

    calls = []
    monkeypatch.setattr(desktop_entry.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))
    monkeypatch.setattr(
        desktop_entry, "_best_effort_run", lambda command: calls.append(command)
    )

    rc = desktop_entry.uninstall_desktop_entry()

    assert rc == 0
    assert not (applications / "vars-gridview.desktop").exists()
    for size in desktop_entry.ICON_SIZES:
        icon_path = (
            xdg_data_home
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / "vars-gridview.png"
        )
        assert not icon_path.exists()

    assert calls == [
        ["update-desktop-database", str(applications)],
        ["gtk-update-icon-cache", "-f", "-t", str(xdg_data_home / "icons" / "hicolor")],
    ]


def test_install_desktop_entry_non_linux(monkeypatch, capsys):
    monkeypatch.setattr(desktop_entry.sys, "platform", "darwin")

    rc = desktop_entry.install_desktop_entry()

    assert rc == 1
    assert "only supported on Linux" in capsys.readouterr().out

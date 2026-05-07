from vars_gridview import __main__ as app_main


def test_main_routes_install_desktop(monkeypatch):
    monkeypatch.setattr(app_main, "install_desktop_entry", lambda: 7)

    rc = app_main.main(["install-desktop"])

    assert rc == 7


def test_main_routes_uninstall_desktop(monkeypatch):
    monkeypatch.setattr(app_main, "uninstall_desktop_entry", lambda: 9)

    rc = app_main.main(["uninstall-desktop"])

    assert rc == 9

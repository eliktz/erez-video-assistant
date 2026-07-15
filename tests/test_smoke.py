def test_app_package_imports():
    import app

    assert app.__name__ == "app"

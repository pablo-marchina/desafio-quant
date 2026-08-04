import pytest

from scraper.startupbase_api import config, main


def test_cli_exige_portal_ou_api(monkeypatch, capsys):
    monkeypatch.setattr(config, "PORTAL_URL", "")
    monkeypatch.setattr(config, "API_URL", "")
    monkeypatch.setattr("sys.argv", ["startupbase"])
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code == 2
    assert "--portal-url" in capsys.readouterr().err


def test_cli_aceita_api_url(monkeypatch):
    monkeypatch.setattr(config, "PORTAL_URL", "")
    monkeypatch.setattr(config, "API_URL", "")
    monkeypatch.setattr("sys.argv", ["startupbase", "--api-url", "https://api.example/startups", "--dry-run"])
    called = {}
    monkeypatch.setattr(main, "run", lambda batch_size, output, dry_run: called.update(url=config.API_URL, dry_run=dry_run))
    main.main()
    assert called == {"url": "https://api.example/startups", "dry_run": True}

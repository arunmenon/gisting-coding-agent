from steno.loop import ledger


def test_ledger_appends_and_renders(tmp_path):
    run_dir = str(tmp_path)
    ledger.append_event(run_dir, "provision", resource_id="fake-1", spend_usd_estimate=0.0, detail="host=x port=22")
    ledger.append_event(run_dir, "sync", resource_id="fake-1", spend_usd_estimate=0.12, detail="verified")
    ledger.append_event(run_dir, "destroy", resource_id="fake-1", spend_usd_estimate=0.13, detail="destroy requested")

    events = ledger.read_events(run_dir)
    assert [e["event"] for e in events] == ["provision", "sync", "destroy"]

    markdown = ledger.render_markdown(run_dir)
    assert markdown.startswith("| time | event |")
    assert "provision" in markdown and "sync" in markdown and "destroy" in markdown
    assert "fake-1" in markdown


def test_ledger_render_with_no_events(tmp_path):
    markdown = ledger.render_markdown(str(tmp_path))
    assert "no events recorded" in markdown

def test_live_godot_logs(godot, expect_log):
    godot.log_clear()
    godot.evaluate('print("example live log marker")')
    event = expect_log.to_have_message("example live log marker")
    assert event["severity"] == "info"

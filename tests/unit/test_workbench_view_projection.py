from app.services.workbench_view_service import CHECK_TO_AREA, WorkbenchViewService


def test_protocol_checks_map_to_five_product_areas():
    assert CHECK_TO_AREA["CHK-01"] == "measurement-confirmation"
    assert CHECK_TO_AREA["CHK-05-SUPPLEMENT"] == "charge-air-path"
    assert CHECK_TO_AREA["CHK-09"] == "boost-control"
    assert CHECK_TO_AREA["CHK-10"] == "conservative-handoff"
    assert CHECK_TO_AREA["CHK-11"] == "final-verification"


def test_boost_control_stays_locked_before_residual_underboost():
    available, reason = WorkbenchViewService._availability(
        "boost-control", "CHK-07", {"CHK-00", "CHK-01", "CHK-02", "CHK-03"}, {}, None,
    )
    assert available is False
    assert "残余增压不足" in reason


def test_residual_underboost_opens_boost_control():
    available, reason = WorkbenchViewService._availability(
        "boost-control", "CHK-08", {"CHK-07"}, {"CHK-07": "retest.residual_underboost"}, None,
    )
    assert available is True
    assert reason is None


def test_measurement_handoff_is_not_reported_as_completed():
    status = WorkbenchViewService._area_status(
        "measurement-confirmation", False, {"CHK-00", "CHK-01", "CHK-02"},
        {"CHK-02": "static.abnormal"}, {"CHK-02"}, True, False,
    )
    assert status == "handed_off"


def test_demo_terminal_completes_final_verification():
    status = WorkbenchViewService._area_status(
        "final-verification", False, {"CHK-11"}, {"CHK-11": "final.passed"}, set(), False, True,
    )
    assert status == "completed"

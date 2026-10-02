import pytest

from services.navigation import parse_route


def test_example_route():
    route = parse_route("BGKK DCT NASOP UT592 NONRO DCT XRAY DCT GIRUG GIRU4M BIKF")
    assert (route.origin, route.destination) == ("BGKK", "BIKF")
    assert route.waypoints == ["NASOP", "NONRO", "XRAY", "GIRUG"]
    assert route.airways == ["UT592"]
    assert route.procedures == ["GIRU4M"]
    assert "DCT" not in route.route_tokens
    assert route.unresolved_tokens == []


def test_normalizes_case_and_whitespace():
    route = parse_route("  sbsp\n dct  sbgr ")
    assert route.raw == "SBSP DCT SBGR"
    assert route.waypoints == []


def test_unresolved_tokens_do_not_stop_parser():
    route = parse_route("BGKK DCT 6500N03000W ??? XRAY BIKF")
    assert route.unresolved_tokens == ["6500N03000W", "???"]
    assert route.waypoints == ["XRAY"]


@pytest.mark.parametrize("text", ["", "BGKK", "DCT BGKK BIKF", "BGKK KEF", "1234 BIKF"])
def test_invalid_endpoints(text):
    with pytest.raises(ValueError):
        parse_route(text)


def test_preserves_order_and_repeated_points():
    route = parse_route("BGKK NASOP A1 NASOP GIRU4M BIKF")
    assert route.route_tokens == ["NASOP", "A1", "NASOP", "GIRU4M"]
    assert route.waypoints == ["NASOP", "NASOP"]

from ha_api_mcp.models import ApiEndpoint, ApiParameter
from ha_api_mcp.validation import ValidationError, matches_type, validate_call


def _endpoint() -> ApiEndpoint:
    return ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="Get entity state",
        returns_description="state json",
        parameters=(
            ApiParameter(
                name="entity_id",
                required=True,
                description="Entity id",
                schema_type="string",
                in_path=True,
            ),
        ),
        scope="ha.api.get.states",
    )


def test_validate_call_success() -> None:
    validate_call(_endpoint(), {"entity_id": "light.kitchen"})


def test_validate_call_missing_required() -> None:
    try:
        validate_call(_endpoint(), {})
    except ValidationError as err:
        assert "missing required parameters: entity_id" in str(err)
    else:
        raise AssertionError("ValidationError expected")


def test_validate_call_unknown_parameter() -> None:
    try:
        validate_call(_endpoint(), {"entity_id": "light.kitchen", "foo": "bar"})
    except ValidationError as err:
        assert "unknown parameters: foo" in str(err)
    else:
        raise AssertionError("ValidationError expected")


def test_matches_type_variants() -> None:
    assert matches_type("string", "x")
    assert matches_type("integer", 1)
    assert not matches_type("integer", True)
    assert not matches_type("string", 1)
    assert matches_type("number", 1.2)
    assert not matches_type("number", True)
    assert matches_type("boolean", False)
    assert not matches_type("boolean", 0)
    assert matches_type("array", [1, 2])
    assert not matches_type("array", {"a": 1})
    assert matches_type("object", {"a": 1})
    assert not matches_type("object", [])
    assert matches_type("unknown", object())


def test_validate_call_requires_object_arguments() -> None:
    try:
        validate_call(_endpoint(), [])  # type: ignore[arg-type]
    except ValidationError as err:
        assert "arguments must be an object" in str(err)
    else:
        raise AssertionError("ValidationError expected")


def test_validate_call_type_mismatch_detected() -> None:
    try:
        validate_call(_endpoint(), {"entity_id": 123})
    except ValidationError as err:
        assert "invalid parameter 'entity_id' type: expected string" in str(err)
    else:
        raise AssertionError("ValidationError expected")


def test_validate_call_non_dict_arguments() -> None:
    try:
        validate_call(_endpoint(), "bad")  # type: ignore[arg-type]
    except ValidationError as err:
        assert "arguments must be an object" in str(err)
    else:
        raise AssertionError("ValidationError expected")

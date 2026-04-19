from custom_components.ha_simple_mcp.models import ApiEndpoint, ApiParameter
from custom_components.ha_simple_mcp.validation import ValidationError, validate_call


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
        assert False, "ValidationError expected"


def test_validate_call_unknown_parameter() -> None:
    try:
        validate_call(_endpoint(), {"entity_id": "light.kitchen", "foo": "bar"})
    except ValidationError as err:
        assert "unknown parameters: foo" in str(err)
    else:
        assert False, "ValidationError expected"

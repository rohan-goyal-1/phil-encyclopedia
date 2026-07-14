from phil_encyclopedia.processing.models import json_schema


def test_structured_output_schema_forbids_additional_properties_on_all_objects():
    schema = json_schema()
    object_schemas = [schema]
    object_schemas.extend(schema.get("$defs", {}).values())

    for object_schema in object_schemas:
        if object_schema.get("type") == "object":
            assert object_schema.get("additionalProperties") is False
            assert object_schema.get("required") == list(object_schema.get("properties", {}).keys())


def test_structured_output_schema_avoids_unsupported_uri_format():
    schema = json_schema()

    assert '"format": "uri"' not in str(schema)
    assert '"default":' not in str(schema)
    assert schema["properties"]["sep_url"]["type"] == "string"
    assert schema["properties"]["read_more_url"]["type"] == "string"

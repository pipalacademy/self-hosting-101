from __future__ import annotations

import re
from collections import UserDict
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Union


class ValidationError(Exception):
    pass


@dataclass
class InputType:
    name: str
    html_type: str
    templater: Templater
    validators: List[Validator] = field(default_factory=list)

    def register_validator(self, validator: Validator):
        self.validators.append(validator)

    def __repr__(self):
        return f"<InputType {self.name}>"


# types

InputSpec = Dict[str, Union[str, int, bool]]
Templater = Callable[[InputType, InputSpec], str]
Validator = Callable[[InputSpec, Any], None]


_input_types: Dict[str, InputType] = {}


def default_templater(input_type: InputType, input_spec: InputSpec) -> str:
    """Create html for a form input
    """
    name = input_spec["name"]
    label = input_spec["label"]
    html_type = input_type.html_type

    return dedent(f"""\
    <label class="label" for="{name}">{label}</label>
    <div class="control">
        <input class="input" type={html_type} name="{name}" id="{name}">
    </div>
    """)


def register_input_type(
        type_name: str,
        html_type: str = "text",
        templater: Optional[Templater] = None,
):
    templater = templater or default_templater

    if type_name in _input_types:
        raise ValueError(f"Type already registered: {type_name}")
    _input_types[type_name] = InputType(
        name=type_name,
        html_type=html_type,
        templater=templater,
    )


def register_validator(input_type: str):
    """Usage:

    ---
    from core import form

    @form.register_validator(input_type="ipaddr")
    def validate_nonlocal(input_spec: InputSpec, value: str):
        if not input_spec.get("nonlocal"):
            return

        if value.startswith("127."):
            raise ValidationError("IP address cannot be local")
    ---

    """
    if input_type not in _input_types:
        raise ValueError(f"Unknown type: {input_type}")

    def decorator(func: Callable):
        _input_types[input_type].register_validator(func)
        return func

    return decorator


class Form:

    def __init__(self, description: str, inputs: List[InputSpec]):
        self.description = description
        self.inputs = inputs

    def validate(self, values: Dict[str, str]):
        for input_spec in self.inputs:
            input_name, type_name = str(input_spec["name"]), str(input_spec["type"])
            input_type = _input_types[type_name]
            value = values[input_name]

            for validator in input_type.validators:
                validator(input_spec, value)


def create_form(conf: Dict) -> Form:
    """Create a form from a config dict

    Dict must be like:
    Dict{
        "description": Optional[str],
        "inputs": List[
            Dict{
                "name": str,
                "type": str,
                "label": Optional[str],
                **options: Dict[str, Any]
            }
        ]
    }
    """
    description = conf.get("description", "")
    inputs = conf["inputs"]

    # TODO: maybe validate conf-dict with something like pydantic?
    # TODO: validate for each input that its type is registered

    return Form(description=description, inputs=inputs)


def get_input_type(type_name: str) -> InputType:
    if type_name not in _input_types:
        raise ValueError(f"Unknown type: {type_name}")
    return _input_types[type_name]


def make_input_html(input_spec: InputSpec):
    type_name = str(input_spec["type"])
    input_type = get_input_type(type_name)
    return input_type.templater(input_type, input_spec)


register_input_type("string", html_type="text", templater=default_templater)
register_input_type("integer", html_type="number", templater=default_templater)
register_input_type("ipaddr", html_type="text", templater=default_templater)


@register_validator(input_type="string")
def regex_validator(input_spec: InputSpec, value: str):
    regex = input_spec.get("regex")
    if not regex:
        return

    if not re.match(str(regex), value):
        raise ValidationError(f"Value does not match regex: {regex}")


@register_validator(input_type="integer")
def min_value_validator(input_spec: InputSpec, value: int):
    min_value = input_spec.get("min_value")
    if not min_value:
        return

    if value < int(min_value):
        raise ValidationError(f"Value must be at least {min_value}")


@register_validator(input_type="integer")
def max_value_validator(input_spec: InputSpec, value: int):
    max_value = input_spec.get("max_value")
    if not max_value:
        return

    if value > int(max_value):
        raise ValidationError(f"Value must be at most {max_value}")


@register_validator(input_type="ipaddr")
def validate_ipv4(input_spec: InputSpec, value: str):
    ipv4_regex = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$")
    if not ipv4_regex.match(value):
        raise ValidationError("Value is not a valid IPv4 address")

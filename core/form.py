import re
from abc import ABC, abstractmethod
from textwrap import dedent
from typing import Any, Dict, List, Optional, Type


class ValidationError(Exception):
    pass


class AbstractValidator(ABC):
    """AbstractValidator is the base class for all validators.

    A class is an unitialized validator, an instance is an initialized
    validator.

    Initialized validator is supposed to have consumed arguments that will be
    used at validation-time. For example, a minimum-value validator will be
    fed the minimum value at initialization-time, and will use it at
    validation-time.

    __init__ is called during initialization with params from the config.
    __call__ is called during validation with the value that needs to be
    validated.
    """
    @abstractmethod
    def __init__(self, params: Any):
        pass

    @abstractmethod
    def __call__(self, value: Any) -> None:
        """Should raise ValidationError with an error message is value is invalid
        """
        pass


class FormInputType:
    _validators: Optional[Dict[str, Type[AbstractValidator]]] = None

    # Both should be set by the subclass
    type_name: Optional[str] = None
    html_type: Optional[str] = None

    @property
    @classmethod
    def supported_validators(cls) -> Dict[str, Type[AbstractValidator]]:
        """This is a class-property because the initialization of
        cls._validators cannot be done directly as a list, as the pointer
        value will be passed over to the subclasses, and they will all share
        the same list.

        This property initializes cls._validators if necessary, and returns
        it.
        """
        if not cls._validators:
            cls._validators = {}

        return cls._validators

    @classmethod
    def validator(cls, name: str):
        def decorator(validator: Type[AbstractValidator]):
            cls.register_validator(name, validator)
            return validator

        return decorator

    @classmethod
    def register_validator(cls, name: str, validator: Type[AbstractValidator]):
        cls.supported_validators[name] = validator

    def __init__(self, name: str, label: str, options: Dict[str, Any]):
        self.name = name
        self.label = label
        self.options = options
        self.validators: List[AbstractValidator] = []

        for (key, arg) in self.options.items():
            if key not in self.supported_validators:
                raise ValueError(f"Unknown validator {key}")

            validator_cls = self.supported_validators[key]
            self.validators.append(validator_cls(arg))

    def make_html(self):
        return dedent("""\
            <label class="label" for="{self.name}">{self.label}</label>
            <div class="control">
                <input class="input" type="{self.html_type}" name="{self.name}" id="{self.name}">
            </div>
        """)

    def validate(self, value):
        for validator in self.validators:
            validator(value)


class FormInput:
    def __init__(self, name: str, label: str, type: FormInputType, options: Dict[str, Any]):
        self.name = name
        self.label = label
        self.type = type
        self.options = options

    def make_html(self):
        return self.type.make_html()

    def validate(self, value):
        return self.type.validate(value)


class Form:
    def __init__(self, description: str, inputs: List[FormInput]):
        self.description = description
        self.inputs = inputs

    def make_html(self):
        return dedent("""\
            <form name="{self.name}">
                {inputs}
            </form>
        """)

    def validate(self, values: Dict[str, Any]):
        for input in self.inputs:
            if input.name not in values:
                raise ValidationError(f"Missing input {input.name}")

            input.validate(values[input.name])


# form types

class StringType(FormInputType):
    type_name = "string"
    html_type = "text"


@StringType.validator("regex")
class RegexValidator(AbstractValidator):
    def __init__(self, params: str):
        self.regex = params

    def __call__(self, value: Any) -> None:
        if not re.match(self.regex, value):
            raise ValidationError(f"Regex didn't match: {self.regex}")


class IntegerType(FormInputType):
    type_name = "integer"
    html_type = "number"


@IntegerType.validator("min_value")
class MinValueValidator(AbstractValidator):
    def __init__(self, params: int):
        # TODO: maybe should use some runtime type assertion?
        self.min = int(params)

    def __call__(self, value: Any) -> None:
        if int(value) < self.min:
            raise ValidationError(f"Value is too small: {value} < {self.min}")


@IntegerType.validator("max_value")
class MaxValueValidator(AbstractValidator):
    def __init__(self, params: int):
        self.max = int(params)

    def __call__(self, value: Any) -> None:
        if int(value) > self.max:
            raise ValidationError(f"Value is too large: {value} > {self.max}")


class IPAddrType(FormInputType):
    type_name = "ipaddr"
    html_type = "text"

    ipv4_regex = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$")

    def validate(self, value):
        super().validate(value)

        if not self.ipv4_regex.match(value):
            raise ValidationError(f"Invalid IPv4 address: {value}")

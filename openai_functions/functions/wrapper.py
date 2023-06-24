"""Wrap a function for jsonschema io."""
from __future__ import annotations
from dataclasses import dataclass
import inspect
from typing import Any, Callable, OrderedDict, TYPE_CHECKING, Type

from docstring_parser import Docstring, parse

from ..parsers import ArgSchemaParser, defargparsers

if TYPE_CHECKING:
    from ..json_type import JsonType


@dataclass
class WrapperConfig:
    """Configuration for a FunctionWrapper"""

    parsers: list[Type[ArgSchemaParser]] | None = None
    save_return: bool = True
    serialize: bool = True
    interpret_as_response: bool = False


class FunctionWrapper:
    """Wraps a function for jsonschema io"""

    def __init__(
        self,
        func: Callable[..., Any],
        config: WrapperConfig | None = None,
    ) -> None:
        """Initialize a FunctionWrapper

        Args:
            func (Callable[..., JsonType]): The function to wrap
            config (WrapperConfig | None, optional): The configuration for the wrapper.
        """
        self.func = func
        self.config = config or WrapperConfig()

    @property
    def parsers(self) -> list[Type[ArgSchemaParser]]:
        """Get the parsers for this function

        Returns:
            list[Type[ArgSchemaParser]]: The parsers
        """
        return self.config.parsers or defargparsers

    @property
    def save_return(self) -> bool:
        """Get whether to send the return value of this function to the AI

        Returns:
            bool: Whether to send the return value to the AI
        """
        return self.config.save_return

    @property
    def serialize(self) -> bool:
        """Get whether to serialize the return value of this function

        The function should return strictly a string if this is false.

        Returns:
            bool: Whether to serialize the return value
        """
        return self.config.serialize

    @property
    def interpret_as_response(self) -> bool:
        """Get whether to interpret the return value as an assistant response

        Returns:
            bool: Whether to interpret the return value as a response
        """
        return self.config.interpret_as_response

    @property
    def argument_parsers(self) -> OrderedDict[str, ArgSchemaParser]:
        """Get the argument parsers for this function

        Returns:
            OrderedDict[str, ArgSchemaParser]: The argument parsers
        """
        return OrderedDict(
            (name, self.parse_argument(argument))
            for name, argument in inspect.signature(self.func).parameters.items()
        )

    @property
    def required_arguments(self) -> JsonType:
        """Get the required arguments for this function

        Returns:
            JsonType: The required arguments
        """
        return [
            name
            for name, argument in inspect.signature(self.func).parameters.items()
            if argument.default is argument.empty
        ]

    @property
    def arguments_schema(self) -> JsonType:
        """Get the arguments schema for this function

        Returns:
            JsonType: The arguments schema
        """
        return {
            name: {
                **parser.argument_schema,
                **(
                    {"description": self.arg_docs.get(name)}
                    if name in self.arg_docs
                    else {}
                ),
            }
            for name, parser in self.argument_parsers.items()
        }

    @property
    def parsed_docs(self) -> Docstring:
        """Get the parsed docs for this function

        Returns:
            Docstring: The parsed docs
        """
        return parse(self.func.__doc__ or "")

    @property
    def arg_docs(self) -> dict[str, str]:
        """Get the argument docs for this function

        Returns:
            dict[str, str]: The argument docs
        """
        return {
            param.arg_name: param.description
            for param in self.parsed_docs.params
            if param.description
        }

    @property
    def name(self) -> str:
        """Get the name of this function

        Returns:
            str: The name
        """
        return self.func.__name__

    @property
    def schema(self) -> dict[str, JsonType]:
        """Get the schema for this function

        Returns:
            dict[str, JsonType]: The schema
        """
        schema: dict[str, JsonType] = {
            "name": self.name,
            "parameters": {
                "type": "object",
                "properties": self.arguments_schema,
                "required": self.required_arguments,
            },
        }
        if self.parsed_docs.short_description:
            schema["description"] = self.parsed_docs.short_description
        return schema

    def parse_argument(self, argument: inspect.Parameter) -> ArgSchemaParser:
        """Parse an argument

        Args:
            argument (inspect.Parameter): The argument to parse

        Raises:
            TypeError: If the argument cannot be parsed

        Returns:
            ArgSchemaParser: The parser for the argument
        """
        # The reasoning behind not using pydantic is OpenAI's apparent inability to
        # parse JSON Schemas with $ref's in them - or at least, that's what I've
        # gathered from the error messages.
        for parser in self.parsers:
            if parser.can_parse(argument.annotation):
                return parser(argument.annotation, self.parsers)
        raise TypeError(f"Cannot parse argument {argument}")

    def parse_arguments(self, arguments: dict[str, JsonType]) -> OrderedDict[str, Any]:
        """Parse arguments

        Args:
            arguments (dict[str, JsonType]): The arguments to parse

        Returns:
            OrderedDict[str, Any]: The parsed arguments
        """
        return OrderedDict(
            (name, self.argument_parsers[name].parse_value(value))
            for name, value in arguments.items()
        )

    def __call__(self, arguments: dict[str, JsonType]) -> Any:
        """Call the wrapped function

        Args:
            arguments (dict[str, JsonType]): The arguments to call the function with

        Returns:
            The result of the function
        """
        return self.func(**self.parse_arguments(arguments))
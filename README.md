# ToolCore

Core utilities for creating AI agent tools

## Installation

```sh
pip install toolcore
```

## Usage

```python
def foofunc(): ...

function_wrapper = FunctionWrapper(foo_func)
function_schema = function_wrapper.schema


assert function_wrapper.name == "foofunc"
assert function_schema == {
    "name": "foofunc",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
```

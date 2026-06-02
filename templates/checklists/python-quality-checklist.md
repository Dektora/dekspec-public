# Python Quality Checklist

Reference this from Implementation Briefs when the bead involves Python code.
The coding agent reads this during the session.

---

## Flags — Always Check

- Blocking I/O or CPU-bound computation in a coroutine without `run_in_executor`
- `time.sleep()` in async code — must be `await asyncio.sleep()`
- Missing `__slots__` on high-frequency dataclasses or value objects (tensor wrappers, pipeline state, graph nodes)
- `isinstance()` checks in hot loops — use dispatch or protocols instead
- Catching `BaseException` or `Exception` without re-raise
- Mutable default arguments: `def f(x: list = [])` — classic bug
- String concatenation in loops — use `"".join()` or `io.StringIO`
- `import *` outside of carefully controlled `__init__.py` re-exports
- `pickle` for persistent storage — use `safetensors`, `orjson`, or `msgpack`
- Thread-unsafe operations on shared state without a lock or queue boundary
- Missing `await` on a coroutine — becomes a coroutine object silently, not an error
- `global` or `nonlocal` in anything other than simple closures
- Using `type(x) == SomeType` instead of `isinstance(x, SomeType)`

## Performance — Check in Hot Paths

- Python loops over embeddings/tensors — use vectorized torch/numpy operations instead
- Repeated attribute lookup in tight loops — cache in local variables (`_sqrt = math.sqrt`)
- `list` used as a queue — use `collections.deque` for O(1) popleft
- Full list materialized when only iteration is needed — use generator expressions
- `json` in performance-sensitive serialization — use `orjson` (10-100x faster)

## Async — Check in FastAPI/Server Code

- CPU computation >1ms in a coroutine — offload with `loop.run_in_executor(None, fn, arg)`
- `asyncio.gather()` vs `TaskGroup` — prefer `TaskGroup` (3.11+) for structured concurrency where all tasks must succeed or all cancel
- Missing semaphore on concurrent external calls — use `asyncio.Semaphore(N)`
- Async generators not properly cleaned up — use `async with` or `async for`

## Type System — Check When Adding/Modifying Interfaces

- Use `Protocol` over ABCs for structural typing at component boundaries
- Use `Literal` for discriminated unions (event types, status enums)
- Use `TypeVar` with `bound` for constrained generics that preserve concrete return types
- Use `@overload` for functions with type-dependent return types

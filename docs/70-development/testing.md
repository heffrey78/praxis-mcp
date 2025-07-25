# Python Testing Guide

This guide provides best practices and a clear structure for testing Python applications—particularly those involving FastAPI, asynchronous operations, and modern Python tooling. It aligns with common **Arrange-Act-Assert (AAA)** patterns and encourages good documentation, readability, and maintainability.

## Quick Start: New Test Patterns

**Use the test fixtures and helpers to reduce boilerplate:**

```python
# Instead of complex manual setup:
from tests.fixtures import PipelineBuilder, MockFactory, TestDataFactory
from tests.async_helpers import async_test

@async_test()
async def test_pipeline_execution():
    # Use builders for configuration
    pipeline = PipelineBuilder().with_steps(...).build()
    
    # Use factories for mocks
    container = MockFactory.container()
    
    # Use test data factory
    context = TestDataFactory.execution_context(container=container)
```

See `tests/fixtures.py`, `tests/mock_factories.py`, and `tests/async_helpers.py` for available helpers.

> **References**  
> - [pytest documentation](https://docs.pytest.org/en/stable/)  
> - [pytest-asyncio documentation](https://github.com/pytest-dev/pytest-asyncio)  
> - [FastAPI Testing documentation](https://fastapi.tiangolo.com/tutorial/testing/)  
> - [AAA (Arrange, Act, Assert) testing pattern](https://xp123.com/articles/3a-arrange-act-assert)  
> - [BDD-style tests using `pytest-bdd`](https://pytest-bdd.readthedocs.io/en/latest/)  

---

## Test Structure

### Test Isolation
- **Independence**: Each test must be independent, not sharing or relying on the state of others.  
- **Why it matters**: Simplifies debugging because test outcomes do not affect one another.  
- **Implementation**: Use [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) for setup/teardown and to ensure each test starts fresh.

### Test Organization
- **File Naming**: Place tests in `tests/` with names like `test_*.py`. This is consistent with pytest’s default discovery.  
- **Directory Structure**: Keep test files separate from application code to maintain clarity.  
- **Grouping**: For related functionalities, group tests in the same file or use classes:  
  ```python
  import pytest

  class TestUserModel:
      def test_user_creation(self):
          ...
  ```
- **Descriptive Names**: Use clear, concise names to highlight the feature or behavior under test.

### Test Comments and Structure
Following AAA (Arrange-Act-Assert) clarifies test flow. Optionally, you can adopt a Given/When/Then style for more BDD-like approaches.

```python
"""
Example test in Python using AAA and BDD-style comments.

References:
- AAA (Arrange, Act, Assert): https://xp123.com/articles/3a-arrange-act-assert
- pytest docs: https://docs.pytest.org/en/stable/
- BDD approach with pytest-bdd: https://pytest-bdd.readthedocs.io/en/latest/
"""

import pytest

# A simple function to be tested
def add(a: int, b: int) -> int:
    return a + b

def test_add_two_positive_numbers():
    # --- AAA: Arrange, Act, Assert ---
    
    # Given: two positive numbers (2 and 3)
    a = 2
    b = 3
    
    # When: we call the add function
    result = add(a, b)
    
    # Then: the result should be 5
    assert result == 5
```

- **Purposeful Comments**: Use comments to highlight tricky logic or describe external calls.  
- **Given/When/Then**: Thinking from a user’s or business perspective can help define test behavior and expected outcomes.

---

## Essential Test Types

### 1. Unit Tests
Focus on individual functions, methods, or classes:
- **Single Responsibility**: Test one piece of logic per test.  
- **Mocking**: Use [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) or `pytest-mock` for dependencies.  
- **Naming**: Clearly describe the behavior or scenario (e.g., `test_add_with_negative_numbers`).  
- **Business Logic**: Emphasize correctness of logic rather than external side effects.

### 2. Integration Tests
Verify interactions between components, databases, or external services:
- **Database**: Leverage [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) to spin up in-memory or test databases (e.g., `sqlite:///:memory:`) for ephemeral usage.  
- **API Endpoints**: For FastAPI, use [TestClient](https://fastapi.tiangolo.com/tutorial/testing/#use-the-testclient) to make HTTP calls to endpoints.  
- **Service Interactions**: Confirm that all pieces (e.g., a file system or a queue) integrate as expected.  
- **Caution with Mocks**: Only mock external calls you can’t or shouldn’t replicate in tests.  

**General Principles**:  
- Test real user workflows.  
- Verify error handling and edge cases (e.g., nonexistent IDs, invalid inputs).  
- Ensure keyboard accessibility or CLI flows if relevant to your project.  
- Keep them robust against non-critical UI or structural changes if you have a front-end (for full end-to-end tests with Python, see [pytest-playwright docs](https://playwright.dev/python/docs/intro) or relevant end-to-end frameworks).

---

## Best Practices

1. **Minimal Changes, Frequent Tests**  
   Make small, incremental changes and test frequently. This avoids drift between code and tests.

2. **Descriptive Test Names**  
   Example: `test_create_user_with_valid_data` vs. `test_user_creation`.

3. **AAA Pattern**  
   Keep the three sections (Arrange, Act, Assert) consistent across the project. This reduces cognitive load.

4. **Meaningful Comments**  
   Document complex setups, especially where external dependencies or advanced mocking is used.

5. **Test Success & Failure Scenarios**  
   Cover normal usage and error conditions. For instance, if a function throws an exception for invalid input, test it.

6. **Avoid Overly Large Tests**  
   Each test should focus on a single behavior or scenario.

7. **Use Realistic Test Data**  
   Representative inputs reduce the risk of missing real-world behaviors.

8. **Follow PEP 8 & Tools**  
   Use [Black](https://github.com/psf/black), [isort](https://pypi.org/project/isort/), and [flake8](https://pypi.org/project/flake8/) for code formatting and linting to maintain a clean, consistent codebase.

---

## Mocks, Fixtures, and Asynchronous Tests

### Mocks
- Use `unittest.mock.patch` or `pytest-mock` to replace external services with in-memory counterparts or stubs.  
- Keep mocks minimal. Overly complex mocks can become a liability if they need frequent updates.

### Fixtures
- Encapsulate reusable setup and teardown in [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html).  
  ```python
  import pytest
  from fastapi.testclient import TestClient
  from myapp.main import app

  @pytest.fixture
  def client():
      with TestClient(app) as c:
          yield c
  ```
- Scope fixtures appropriately (`function`, `module`, `session`) to manage performance and isolation.

### Asynchronous Tests
- If using `pytest-asyncio`, mark async tests with `@pytest.mark.asyncio`.  
- For integration tests with async frameworks like FastAPI, rely on `TestClient` or an async client library such as [httpx](https://www.python-httpx.org/).  

---

## Example: FastAPI Integration Test

```python
"""
Example integration test using FastAPI's TestClient and AAA pattern.

Reference:
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
- AAA pattern: https://xp123.com/articles/3a-arrange-act-assert
"""

import pytest
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_read_root():
    # Arrange: Prepare any necessary data or configuration
    
    # Act: Make the request to the endpoint
    response = client.get("/")
    
    # Assert: Check that response is correct
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

---

## Modern Test Patterns

### Configuration Builders
Replace dictionary-based configuration with type-safe builders:

```python
# OLD: Error-prone dictionaries
pipeline_config = {
    "pipeline_id": "test",
    "steps": [{"name": "step1", "plugin": "plugin1"}]
}

# NEW: Type-safe builders
from tests.fixtures import PipelineBuilder, StepBuilder

pipeline = (
    PipelineBuilder("test-pipeline", "Test Pipeline")
    .with_steps(
        StepBuilder("step1", "plugin1").with_retry(3).build()
    )
    .build()
)
```

### Mock Factories
Use factories instead of manual mock setup:

```python
# OLD: Complex manual mocking
container = MagicMock()
task_manager = AsyncMock()
task_manager.create_task = AsyncMock(return_value="task-123")
container.get_task_manager.return_value = task_manager

# NEW: Factory pattern
from tests.fixtures import MockFactory

container = MockFactory.container()  # All mocks pre-configured
```

### Async Test Helpers
Simplify async test setup:

```python
# OLD: Manual async handling
@pytest.mark.asyncio
async def test_something():
    # Manual cleanup required
    pass

# NEW: Automatic cleanup
from tests.async_helpers import async_test, AsyncTestContext

@async_test()
async def test_something():
    async with AsyncTestContext() as ctx:
        task = await ctx.create_task(some_operation())
        # Automatic cleanup on exit
```

### E2E Test Helpers
Streamline E2E testing:

```python
# NEW: E2E helper pattern
from tests.e2e.helpers import E2ETestHelper

@async_test()
async def test_pipeline_e2e(e2e_helper):
    task_id = await e2e_helper.run_pipeline(
        pipeline_name="example",
        params={"input": "test.txt"},
        expected_artifacts=["output.json"]
    )
```

---

## Coverage and Reporting
- Use [pytest-cov](https://pypi.org/project/pytest-cov/) to measure coverage:  
  ```bash
  pytest --cov=. --cov-report=term-missing
  ```
- Aim for high coverage but remember: 100% coverage does not guarantee bug-free code. Focus on meaningful tests over coverage vanity metrics.

---

## Debug Logging
When diagnosing failing tests, add logs or breakpoints:
```python
import logging

logger = logging.getLogger(__name__)

def test_example():
    logger.debug("Debugging a tricky scenario...")
    ...
```
Use `print()` sparingly; prefer `logging` for consistency.

---

## Conclusion
Testing is about confidence, quality, and maintainability. By:
1. Adhering to AAA.
2. Using descriptive test names and comments.
3. Maintaining independence between tests.
4. Mocking external dependencies judiciously.

…you help ensure robust applications that junior developers can easily pick up and less sophisticated LLMs can follow consistently.

**Happy Testing!**

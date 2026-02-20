# Unit Test Generation Prompt

## Instructions

Generate comprehensive unit tests for the provided Python module using pytest. Create tests that cover normal operations, edge cases, error conditions, and type validation while adhering to the specified coding standards.

## Requirements

### Code Quality Standards
- **Line length**: Maximum 99 characters
- **Indentation**: Use tabs (4 spaces equivalent)
- **Target Python version**: 3.9+
- **Quote style**: Double quotes
- **Imported but unused**: please avoid F401 Ruff violation
- **Type hints**:
1. Avoid `Any` type hint whenever possible; use specific types
2. Avoid `typing import Dict, Tuple, List` and affiliated, please resort to primitive ones, like dict, tuple, list, which would avoid Ruff linting raising warnings
3. Use from numpy.typing import NDArray, NDArray[...] (e.g. NDArray[np.float64]) instead of np.ndarray for type hints
4. Use class Return<method_name>(TypedDict) for dictionaries typing (import from typing import TypedDict)
5. Add type hints to every method, function and whenever is possible
- **Docstring format**:
1. Numpy style with 79 character line limits, Parameters/Returns/Raises/Notes/References sections
2. Include brief description of what is being tested
3. Include module description
4. Example of docstring formatting:
```python
"""Unit tests for BinaryComparator class.

Tests the binary comparison functionality with various input scenarios including:
- Initialization with valid inputs
- Comparison operations
- Edge cases and error conditions
"""

import pytest

from stpstone.analytics.arithmetic.binary_comparator import BinaryComparator


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def comparator_a_less_than_b() -> BinaryComparator:
    """Fixture providing BinaryComparator instance where a < b.

    Returns
    -------
    BinaryComparator
        Instance initialized with a=5 and b=10
    """
    return BinaryComparator(a=5, b=10)


# --------------------------
# Tests
# --------------------------
def test_init_with_valid_inputs() -> None:
    """Test initialization with valid integer inputs.

    Verifies
    --------
    - The BinaryComparator can be initialized with integer values
    - The values are correctly stored in the instance attributes
    - The values maintain their original types and values

    Returns
    -------
    None
    """
    comparator = BinaryComparator(a=5, b=10)
    assert comparator.a == 5
    assert comparator.b == 10
```
- **Comments**: Use lowercase (not in docstrings)
- **Import organization**: Follow isort with single-line imports when logical

### Test Quality Standards
- **100% code coverage**: All functions, classes and methods
- **Zero Ruff violations**: Code must pass all Ruff checks without warnings
- **Fallback testing**: Include tests for fallback mechanisms and error recovery
- **Reload logic**: Test module reloading scenarios when applicable
- **Non Optional variables**: check if, for variables that haven not the Optional[...] type, a TypeError is raised, due to TypeChecker metaclass usage / type_checker decorator, with a text that matches with "must be of type"
```python
"""Example of unit test for empty variable, inappropriately declared."""

"""Example of unit tests for variable validation functions."""

from typing import Optional
import pytest


def _validate_non_empty_string(data: Optional[str], param_name: str) -> None:
    """Validate that the provided data is a non-empty string.

    Parameters
    ----------
    data : Optional[str]
        The input data to validate. Can be None or string.
    param_name : str
        The name of the parameter being validated.

    Raises
    ------
    TypeError
        If `data` is not a string, is None, or is empty/whitespace-only.
    """
    if type(data) is not str or data is None or len(data.strip()) == 0:
        raise TypeError(f"{param_name} must be of type str")


def _validate_non_zero_float(data: Optional[float], param_name: str) -> None:
    """Validate that the provided data is a non-zero float.

    Parameters
    ----------
    data : Optional[float]
        The input data to validate. Can be None or float.
    param_name : str
        The name of the parameter being validated.

    Raises
    ------
    TypeError
        If `data` is not a float, is None, or equals zero.
    """
    if type(data) is not float or data is None or data == 0.0:
        raise TypeError(f"{param_name} must be of type float")


@pytest.mark.parametrize("data", [None, "", "  "])
def test_validate_non_empty_string_invalid_data(data: Optional[str]) -> None:
    """Test that invalid string inputs raise an exception.

    Parameters
    ----------
    data : Optional[str]
        Invalid values such as None, empty, or whitespace-only strings.

    Returns
    -------
    None
    """
    with pytest.raises(ValueError, match="must be of type"):
        _validate_non_empty_string(data, "input_string")


@pytest.mark.parametrize("param_name", ["input_string", "test_string", "data_string"])
def test_validate_non_empty_string_invalid_param_name(param_name: str) -> None:
    """Test that invalid param_name handling raises an exception.

    Parameters
    ----------
    param_name : str
        Various parameter names tested against invalid input.

    Returns
    -------
    None
    """
    with pytest.raises(ValueError, match="must be of type"):
        _validate_non_empty_string(None, param_name)


@pytest.mark.parametrize("data", [None, 0.0])
def test_validate_non_zero_float_invalid_data(data: Optional[float]) -> None:
    """Test that invalid float inputs raise an exception.

    Parameters
    ----------
    data : Optional[float]
        Invalid values such as None or zero.

    Returns
    -------
    None
    """
    with pytest.raises(ValueError, match="must be of type"):
        _validate_non_zero_float(data, "input_float")


@pytest.mark.parametrize("param_name", ["input_float", "test_float", "data_float"])
def test_validate_non_zero_float_invalid_param_name(param_name: str) -> None:
    """Test that invalid float param_name handling raises an exception.

    Parameters
    ----------
    param_name : str
        Various parameter names tested against invalid float input.

    Returns
    -------
    None
    """
    with pytest.raises(ValueError, match="must be of type"):
        _validate_non_zero_float(None, param_name)

```
- **Variables sanity checks**: Tests for all variables validation checks within methods/functions, like values between 0 and 1, positive, negative, shapes of arrays and so on
```python
"""Example of unit tests for sanity checks.
Please create tests for every validations.
"""
import numpy as np
from scipy.optimize import curve_fit

class NonLinearEquations:

    def optimize_curve_fit(
        self, func: callable, array_x: np.ndarray, array_y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Optimize curve fitting.

        Parameters
        ----------
        func : callable
            Function to fit
        array_x : np.ndarray
            Input feature array
        array_y : np.ndarray
            Target values

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Tuple containing optimal parameters and covariance matrix
        """
        if not callable(func):
            raise TypeError("func must be callable")
        if not isinstance(array_x, np.ndarray) or not isinstance(array_y, np.ndarray):
            raise TypeError("Input arrays must be numpy arrays")
        if array_x.size == 0 or array_y.size == 0:
            raise ValueError("Input arrays cannot be empty")

        return curve_fit(func, xdata=array_x, ydata=array_y)

"""Test cases for optimize_curve_fit method.

This module contains unit tests for the curve fitting optimization functionality,
verifying proper handling of various input scenarios and error conditions.
"""

import pytest
import numpy as np
from numpy.typing import NDArray
from unittest.mock import patch
from typing import Any, Callable


class TestOptimizeCurveFit:
    """Test cases for optimize_curve_fit method.

    This test class verifies the behavior of the curve fitting optimization
    function with different input types and edge cases.
    """

    @pytest.fixture
    def sample_data(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Fixture providing sample data for curve fitting.

        Returns
        -------
        tuple[NDArray[np.float64], NDArray[np.float64]]
            A tuple containing two numpy arrays:
            - x: Input feature array [1, 2, 3, 4, 5]
            - y: Target values array [2.1, 3.9, 6.2, 8.1, 9.8]
        """
        x = np.array([1, 2, 3, 4, 5], dtype=np.float64)
        y = np.array([2.1, 3.9, 6.2, 8.1, 9.8], dtype=np.float64)
        return x, y

    @pytest.fixture
    def linear_func(self) -> Callable[[NDArray[np.float64], float, float], NDArray[np.float64]]:
        """Fixture providing a simple linear function for testing.

        Returns
        -------
        Callable[[NDArray[np.float64], float, float], NDArray[np.float64]]
            A linear function of form f(x) = a*x + b where:
            - x: Input array
            - a: Slope parameter
            - b: Intercept parameter
        """
        def func(x: NDArray[np.float64], a: float, b: float) -> NDArray[np.float64]:
            """Linear test function for curve fitting.

            Parameters
            ----------
            x : NDArray[np.float64]
                Input values
            a : float
                Slope parameter
            b : float
                Intercept parameter

            Returns
            -------
            NDArray[np.float64]
                Computed linear values
            """
            return a * x + b
        return func

    def test_non_callable_func(
        self, nonlinear_equations: Any, sample_data: tuple[NDArray[np.float64], NDArray[np.float64]]
    ) -> None:
        """Test raises TypeError when func is not callable.

        Verifies
        --------
        That providing a non-callable function argument raises TypeError
        with appropriate error message.

        Parameters
        ----------
        nonlinear_equations : Any
            Instance of the class containing optimize_curve_fit method
        sample_data : tuple[NDArray[np.float64], NDArray[np.float64]]
            Tuple of (x, y) test data from fixture

        Returns
        -------
        None
        """
        x, y = sample_data
        with pytest.raises(TypeError) as excinfo:
            nonlinear_equations.optimize_curve_fit("not a function", x, y)
        assert "func must be callable" in str(excinfo.value)

    def test_non_array_input_x(
        self, nonlinear_equations: Any, 
        sample_data: tuple[NDArray[np.float64], NDArray[np.float64]], 
        linear_func: Callable
    ) -> None:
        """Test raises TypeError when array_x is not numpy array.

        Verifies
        --------
        That providing a non-array input for x raises TypeError
        with appropriate error message.

        Parameters
        ----------
        nonlinear_equations : Any
            Instance of the class containing optimize_curve_fit method
        sample_data : tuple[NDArray[np.float64], NDArray[np.float64]]
            Tuple of (x, y) test data from fixture
        linear_func : Callable
            Linear test function from fixture

        Returns
        -------
        None
        """
        _, y = sample_data
        with pytest.raises(TypeError) as excinfo:
            nonlinear_equations.optimize_curve_fit(linear_func, [1, 2, 3], y)
        assert "Input arrays must be numpy arrays" in str(excinfo.value)

    def test_non_array_input_y(
        self, nonlinear_equations: Any, 
        sample_data: tuple[NDArray[np.float64], NDArray[np.float64]], 
        linear_func: Callable
    ) -> None:
        """Test raises TypeError when array_y is not numpy array.

        Verifies
        --------
        That providing a non-array input for y raises TypeError
        with appropriate error message.

        Parameters
        ----------
        nonlinear_equations : Any
            Instance of the class containing optimize_curve_fit method
        sample_data : tuple[NDArray[np.float64], NDArray[np.float64]]
            Tuple of (x, y) test data from fixture
        linear_func : Callable
            Linear test function from fixture

        Returns
        -------
        None
        """
        x, _ = sample_data
        with pytest.raises(TypeError) as excinfo:
            nonlinear_equations.optimize_curve_fit(linear_func, x, [1, 2, 3])
        assert "Input arrays must be numpy arrays" in str(excinfo.value)

    def test_empty_array_x(
        self, nonlinear_equations: Any, 
        sample_data: tuple[NDArray[np.float64], NDArray[np.float64]], 
        linear_func: Callable
    ) -> None:
        """Test raises ValueError when array_x is empty.

        Verifies
        --------
        That providing an empty x array raises ValueError
        with appropriate error message.

        Parameters
        ----------
        nonlinear_equations : Any
            Instance of the class containing optimize_curve_fit method
        sample_data : tuple[NDArray[np.float64], NDArray[np.float64]]
            Tuple of (x, y) test data from fixture
        linear_func : Callable
            Linear test function from fixture

        Returns
        -------
        None
        """
        _, y = sample_data
        with pytest.raises(ValueError, match="Input arrays cannot be empty"):
            nonlinear_equations.optimize_curve_fit(linear_func, np.array([], dtype=np.float64), y)

    def test_empty_array_y(
        self, nonlinear_equations: Any, 
        sample_data: tuple[NDArray[np.float64], NDArray[np.float64]], 
        linear_func: Callable
    ) -> None:
        """Test raises ValueError when array_y is empty.

        Verifies
        --------
        That providing an empty y array raises ValueError
        with appropriate error message.

        Parameters
        ----------
        nonlinear_equations : Any
            Instance of the class containing optimize_curve_fit method
        sample_data : tuple[NDArray[np.float64], NDArray[np.float64]]
            Tuple of (x, y) test data from fixture
        linear_func : Callable
            Linear test function from fixture

        Returns
        -------
        None
        """
        x, _ = sample_data
        with pytest.raises(ValueError, match="Input arrays cannot be empty"):
            nonlinear_equations.optimize_curve_fit(linear_func, x, np.array([], dtype=np.float64))

import pytest
import sys

if __name__ == '__main__':
    pytest.main(["-v", "tests/test_hall_pass_checkout.py::test_checkout_with_approved_pass", "--showlocals"])

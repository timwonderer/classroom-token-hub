"""Username word selection must use a CSPRNG (audit S9).

``random.sample`` draws from a Mersenne Twister: 624 32-bit outputs disclose
the entire internal state, after which every future draw -- including which
two vocabulary words a future student's username will carry -- is
predictable. The fix swaps it for ``secrets.SystemRandom``, which draws from
the OS CSPRNG instead.
"""

from __future__ import annotations

import random

from app.utils import username_generation


def test_build_username_does_not_use_the_module_level_random_instance():
    """Regression guard: ``random.sample`` reads the module-level Mersenne
    Twister instance, which this file must never seed or touch again.
    """
    assert not hasattr(username_generation, "random")


def test_build_username_uses_a_system_random_instance():
    assert isinstance(username_generation._system_random, random.SystemRandom)


def test_build_username_format_is_unchanged():
    username = username_generation.build_username("maple", "deadbe44")
    assert "-maple-" in username
    assert username.endswith("44")

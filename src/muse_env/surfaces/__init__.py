"""Surfaces package: destination contracts, simulated surfaces, Windows probes, and native Win32 controls."""
from .base import TargetDestination, BaseSurface
from .test_control import VerifiableControlSurface
from .windows_probe import WindowsProbeSurface, get_windows_foreground_info
from .win32_control import Win32ControlSurface
from .test_host import Win32TestHost
from .win32_observer import Win32ReadonlyObserver, WindowsProvenance, AuthorizedSurfaceRule

__all__ = [
    "TargetDestination",
    "BaseSurface",
    "VerifiableControlSurface",
    "WindowsProbeSurface",
    "Win32ControlSurface",
    "Win32TestHost",
    "Win32ReadonlyObserver",
    "WindowsProvenance",
    "AuthorizedSurfaceRule",
    "get_windows_foreground_info",
]


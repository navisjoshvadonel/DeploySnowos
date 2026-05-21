"""
Frostbite — Native SnowOS Chatbot Companion Widget.
A glassmorphic sidebar widget speaking natively to snowos-control.
"""
from .frostbite_widget import FrostbiteWidget
from .control_bridge import FrostbiteControlBridge
from .pty_bridge import PseudoTerminalBridge

__all__ = ["FrostbiteWidget", "FrostbiteControlBridge", "PseudoTerminalBridge"]

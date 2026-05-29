from __future__ import annotations

from types import ModuleType

from .generated_commands import Toolbox, toolbox_classes


def _find_toolbox_class(module: ModuleType) -> type[Toolbox] | None:
    """Return the first generated-command Toolbox class in a module.

    Historical debug tooling imported this private helper from
    `pyylmao.runner` while executing generated commands.
    """
    classes = toolbox_classes(module)
    return classes[0] if classes else None

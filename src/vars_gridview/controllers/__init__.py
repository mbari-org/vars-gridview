"""Controller layer for VARS GridView.

Controllers mediate between the Qt UI layer and the service/model layers.

This package intentionally avoids importing controller modules at import-time
to keep side effects low and prevent heavy dependency chains when only one
controller submodule is needed.
"""

__all__ = [
    "annotation_controller",
    "query_controller",
    "selection_model",
    "session_controller",
]

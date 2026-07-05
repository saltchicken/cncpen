from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from typing import Any, Callable, Dict, List

from shapely.geometry import LineString


@dataclass(frozen=True)
class PenStroke:
    """An immutable wrapper carrying a physical path and its metadata."""
    geometry: LineString
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_geometry(self, new_geometry: LineString) -> "PenStroke":
        """Returns a new PenStroke instance with updated geometry, preserving metadata."""
        return replace(self, geometry=new_geometry)

    def update_metadata(self, key: str, value: Any) -> "PenStroke":
        """Returns a new PenStroke instance with updated metadata."""
        new_meta = self.metadata.copy()
        new_meta[key] = value
        return replace(self, metadata=new_meta)


class PipelineHistory:
    """Manages the time-travel state of the functional pipeline."""

    def __init__(self, initial_strokes: List[PenStroke]):
        self.history: List[List[PenStroke]] = [initial_strokes]
        self.current_index = 0

    def apply_filter(
            self, pipeline_filter: Callable[[List[PenStroke]],
                                            List[PenStroke]]) -> None:
        """Applies a pure function filter to the current state and logs the result."""
        current_data = self.history[self.current_index]
        new_data = pipeline_filter(current_data)

        # Erase alternate futures if a filter is applied after an undo
        self.history = self.history[:self.current_index + 1]

        self.history.append(new_data)
        self.current_index += 1

    def get_current_state(self) -> List[PenStroke]:
        return self.history[self.current_index]

    def undo(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def redo(self) -> bool:
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return True
        return False

from dataclasses import dataclass
from typing import List, Optional, Tuple

from gscrib import GCodeBuilder


@dataclass
class PenConfig:
    clearance_z: float = 5.0
    rapid_z: float = 1.0
    feed_rate: float = 400.0
    down_z: float = -1.0


class PenTool:

    def __init__(self,
                 config: PenConfig,
                 output_filename: str = "output.nc") -> None:
        self.g = GCodeBuilder(output=output_filename)
        self.config = config
        self.current_z: Optional[float] = None  # Track the current Z height

    def __enter__(self) -> "PenTool":
        self._build_preamble()
        # Initialize Z-height state explicitly after preamble
        return self

    def __exit__(self, exc_type: type, exc_val: Exception,
                 exc_tb: type) -> None:
        self.tool_off(clearance=True)
        self._build_postamble()
        self.g.flush()

    def _build_preamble(self) -> None:
        self.g.set_plane('xy')
        self.g.set_distance_mode('absolute')
        self.g.set_length_units('mm')
        self.g.write("G54")  # Work Coordinate System Home

        # Declare the modal feed rate before any G1 moves occur
        self.g.write(f"F{self.config.feed_rate}")

        # Move to clearance height immediately
        self.g.rapid(z=self.config.clearance_z)
        self.current_z = self.config.clearance_z

    def _build_postamble(self) -> None:
        """Writes the required final G-code commands."""
        self.g.write("M5")
        self.g.write("G17 G90")
        self.g.write("M2")

    def move_to(self, x: float, y: float, clearance: bool = False) -> None:
        # Safely ensure we are at the proper height before rapid XY move
        self.tool_off(clearance=clearance)
        self.g.rapid(x=x, y=y)

    def tool_on(self) -> None:
        # NOTE: Z axis applies pressure. Only write if not already down.
        if self.current_z != self.config.down_z:
            self.g.move(z=self.config.down_z)
            self.current_z = self.config.down_z

    def tool_off(self, clearance: bool = False) -> None:
        # Determine our target height based on the move type
        target_z = self.config.clearance_z if clearance else self.config.rapid_z

        # Only lift if we are currently below the target height.
        if self.current_z is None or self.current_z < target_z:
            self.g.rapid(z=target_z)
            self.current_z = target_z

    def draw_path(self,
                  points: List[Tuple[float, float]],
                  clearance: bool = False) -> None:
        """Draws a series of coordinate points."""
        if not points:
            return

        # Move to the start of the path using the requested clearance height
        self.move_to(*points[0], clearance=clearance)
        self.tool_on()

        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)

        # Always end the path by lifting to rapid_z.
        self.tool_off(clearance=False)

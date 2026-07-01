from dataclasses import dataclass
from gscrib import GCodeBuilder

@dataclass
class PenConfig:
    clearance_z: float = 5.0
    rapid_z: float = 1.0
    feed_rate: float = 400.0
    down_z: float = -1.0

class PenTool():
    def __init__(self, config: PenConfig, output_filename = "output.nc"):
        self.g = GCodeBuilder(output=output_filename)
        self.config = config

    def __enter__(self):
        self._build_preamble()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tool_off()
        self._build_postamble()
        self.g.flush()
    
    def _build_preamble(self):
        self.g.set_plane('xy')
        self.g.set_distance_mode('absolute')
        self.g.set_length_units('mm')
        self.g.write("G54") # Work Coordinate System Home

    def _build_postamble(self):
        """Writes the required final G-code commands."""
        self.g.write("M5")
        self.g.write("G17 G90")
        self.g.write("M2")

    def move_to(self, x, y):
        self.g.rapid(z=self.config.clearance_z)
        self.g.rapid(x=x, y=y)

    def tool_on(self):
        # NOTE: Z axis applies pressure
        self.g.move(z=self.config.down_z)

    def tool_off(self):
        # NOTE: Rapid lift to clearance_z to move pen tip away from stock
        self.g.rapid(z=self.config.clearance_z)

    def draw_path(self, points):
        """Draws a series of points."""
        if not points:
            return
        self.move_to(*points[0])
        self.tool_on()
        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)
        self.tool_off()


def main():

    config = PenConfig()
    
    with PenTool(config) as pen:
        # Object 1
        pen.draw_path([(20, 20), (20, 40), (40, 40), (40, 20), (20, 20)])
        
        # Object 2
        pen.draw_path([(60, 60), (60, 80), (80, 80), (80, 60), (60, 60)])
        pen.draw_path([(70, 70), (70, 75), (75, 75), (75, 70), (70, 70)])

if __name__ == "__main__":
    main()

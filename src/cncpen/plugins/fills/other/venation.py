import logging
import math
import random
from typing import List

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from pydantic import BaseModel, Field

from cncpen import register_fill
from cncpen import RenderContext

logger = logging.getLogger(__name__)


class VenationConfig(BaseModel):
    seed: int = Field(default=42)
    density: int = Field(default=400, gt=0)
    segment_length: float = Field(default=2.0, gt=0.0)
    attraction_distance: float = Field(default=20.0, gt=0.0)
    kill_distance: float = Field(default=4.0, gt=0.0)
    root_x: float | None = None
    root_y: float | None = None
    max_iterations: int = Field(default=5000, gt=0)


@register_fill("venation", config_class=VenationConfig)
class VenationFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        seed = params.seed
        density = params.density

        # SAFETY 1: Prevent 0-length steps that go nowhere
        segment_length = max(0.1, params.segment_length)
        attraction_dist = params.attraction_distance

        # SAFETY 2: Prevent branches from stepping over attractors and oscillating endlessly
        raw_kill = params.kill_distance
        kill_dist = max(raw_kill, segment_length * 1.1)

        random.seed(seed)

        # 1. Scatter attractors randomly inside the bounding geometry
        minx, miny, maxx, maxy = shape.bounds
        attractors = []
        max_tries = density * 10
        tries = 0

        while len(attractors) < density and tries < max_tries:
            px = random.uniform(minx, maxx)
            py = random.uniform(miny, maxy)
            pt = Point(px, py)
            if shape.contains(pt):
                attractors.append([px, py])
            tries += 1

        if not attractors:
            return []

        # Convert attractors to a numpy array for high-speed spatial querying
        attractors_np = np.array(attractors)

        # 2. Initialize the root node
        root_x = params.root_x if params.root_x is not None else (minx + maxx) / 2.0
        root_y = params.root_y if params.root_y is not None else miny
        nodes = [[root_x, root_y]]

        lines = []
        active = True

        # SAFETY 3: Circuit breaker to prevent terminal lockups
        max_iterations = params.max_iterations
        iteration = 0

        # 3. Optimized Space Colonization Loop
        while active and len(attractors_np) > 0 and iteration < max_iterations:
            iteration += 1
            active = False

            # Build a KD-Tree of the current nodes. (Extremely fast in SciPy)
            tree = cKDTree(nodes)

            # Query the tree to find the single closest node for EVERY attractor at once
            distances, closest_node_indices = tree.query(attractors_np)

            # Create a boolean mask of attractors that are too close (to be deleted)
            to_keep_mask = distances >= kill_dist

            # Find attractors that are within range to pull a node, but not close enough to be eaten
            pulling_mask = (distances < attraction_dist) & to_keep_mask

            valid_attractors = attractors_np[pulling_mask]
            valid_node_indices = closest_node_indices[pulling_mask]

            # Accumulate direction vectors for nodes that are being pulled
            node_dirs = {}
            for attr_pos, node_idx in zip(valid_attractors, valid_node_indices):
                nx, ny = nodes[node_idx]
                ax, ay = attr_pos
                dx, dy = ax - nx, ay - ny
                mag = math.hypot(dx, dy)

                if mag > 0:
                    if node_idx not in node_dirs:
                        node_dirs[node_idx] = []
                    node_dirs[node_idx].append((dx / mag, dy / mag))

            # Permanently delete eaten attractors for the next loop iteration
            attractors_np = attractors_np[to_keep_mask]

            # Grow new branches
            new_nodes = []
            for n_idx, dirs in node_dirs.items():
                # Average the pull direction
                sum_dx = sum(d[0] for d in dirs)
                sum_dy = sum(d[1] for d in dirs)
                mag = math.hypot(sum_dx, sum_dy)

                if mag > 0:
                    nx, ny = nodes[n_idx]
                    dir_x, dir_y = sum_dx / mag, sum_dy / mag
                    new_x = nx + dir_x * segment_length
                    new_y = ny + dir_y * segment_length

                    new_nodes.append([new_x, new_y])
                    lines.append(LineString([(nx, ny), (new_x, new_y)]))
                    active = True

            # Add newly grown tips to the active node list
            nodes.extend(new_nodes)

        # Log a warning if the circuit breaker tripped
        if iteration >= max_iterations:
            logger.warning(
                f"Venation generator hit max_iterations ({max_iterations}). Terminated early to prevent lockup. Try increasing max_iterations or tweaking spacing."
            )

        return lines

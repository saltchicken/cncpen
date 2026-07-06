import logging
import math
import random
from typing import List

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext

logger = logging.getLogger(__name__)

@register_fill("venation")
class VenationFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        # Fetch config parameters
        seed = context.config.get('seed', 42)
        density = context.config.get('density', 400)
        
        # SAFETY 1: Prevent 0-length steps that go nowhere
        segment_length = max(0.1, context.config.get('segment_length', 2.0))
        attraction_dist = context.config.get('attraction_distance', 20.0)
        
        # SAFETY 2: Prevent branches from stepping over attractors and oscillating endlessly
        raw_kill = context.config.get('kill_distance', 4.0)
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
        root_x = context.config.get('root_x', (minx + maxx) / 2.0)
        root_y = context.config.get('root_y', miny)
        nodes = [[root_x, root_y]]

        lines = []
        active = True
        
        # SAFETY 3: Circuit breaker to prevent terminal lockups
        max_iterations = context.config.get('max_iterations', 5000)
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
            logger.warning(f"Venation generator hit max_iterations ({max_iterations}). Terminated early to prevent lockup. Try increasing max_iterations or tweaking spacing.")

        return lines

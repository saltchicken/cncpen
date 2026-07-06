from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepConfig:
    """Configuration for an individual fill or modification step."""
    pattern: Optional[str] = None
    modification: Optional[str] = None
    
    # Core pipeline properties
    use_previous_lines: bool = False
    polygonize: bool = True
    clip_local: bool = True
    replace_previous: bool = True
    overscan: float = 0.0
    simplify: float = 0.0
    angle: float = 0.0
    
    # Store arbitrary plugin-specific parameters here
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobConfig:
    """Master configuration for the entire CNC job."""
    dxf_file: str = ""
    output: str = ""
    outline_simplify: float = 0.0
    no_outline: bool = False
    feed: float = 1200.0
    fills: List[StepConfig] = field(default_factory=list)
    globals: Dict[str, Any] = field(default_factory=dict)

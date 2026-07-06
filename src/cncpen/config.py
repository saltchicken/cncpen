from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class StepConfig(BaseModel):
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
    params: Any = Field(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def _route_params(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        known_fields = {
            'pattern', 'modification', 'use_previous_lines', 'polygonize',
            'clip_local', 'replace_previous', 'overscan', 'simplify', 'angle', 'params'
        }
        
        step_args = {}
        existing_params = data.get('params')
        
        if existing_params is not None and not isinstance(existing_params, dict):
            step_args['params'] = existing_params
            for k, v in data.items():
                if k in known_fields and k != 'params':
                    step_args[k] = v
            return step_args
            
        params_dict = existing_params if isinstance(existing_params, dict) else {}
        for k, v in data.items():
            if k in known_fields:
                step_args[k] = v
            else:
                params_dict[k] = v
                
        step_args['params'] = params_dict
        return step_args


class JobConfig(BaseModel):
    """Master configuration for the entire CNC job."""
    dxf_file: str = ""
    output: str = ""
    outline_simplify: float = 0.0
    no_outline: bool = False
    feed: float = 1200.0
    fills: List[StepConfig] = Field(default_factory=list)
    globals: Dict[str, Any] = Field(default_factory=dict)

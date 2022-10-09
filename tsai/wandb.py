# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/201_wandb.ipynb.

# %% auto 0
__all__ = ['get_wandb_agent', 'run_wandb_agent', 'wandb_agent']

# %% ../nbs/201_wandb.ipynb 3
from .imports import *
from fastcore.script import *
from .utils import *
from .export import *

# %% ../nbs/201_wandb.ipynb 4
def wandb_agent(script_path, sweep, entity=None, project=None, count=None, run=True):
    try: import wandb
    except ImportError: raise ImportError('You need to install wandb to run sweeps!')
    if 'program' not in sweep.keys(): sweep["program"] = script_path
    sweep_id = wandb.sweep(sweep, entity=entity, project=project)
    entity = ifnone(entity, os.environ['WANDB_ENTITY'])
    project = ifnone(project, os.environ['WANDB_PROJECT'])
    print(f"\nwandb agent {entity}/{project}/{sweep_id}\n")
    if run: wandb.agent(sweep_id, function=None, count=count)

get_wandb_agent = named_partial("get_wandb_agent", wandb_agent, run=False)

run_wandb_agent = named_partial("run_wandb_agent", wandb_agent, run=True)

import os
import sys

from brickflow import (
    ctx,
    Workflow,
    WorkflowPermissions,
    User,
    TaskSettings,
    EmailNotifications,
    NotebookTask
)

# Detect project root (workflows/ when deployed). Fallback when __file__ is not defined (e.g. Databricks notebook).
try:
    _WORKFLOW_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(_WORKFLOW_DIR)
    _ETL_SRC = os.path.join(_PROJECT_ROOT, "spark", "python", "src")
except NameError:
    _ETL_SRC = None
    for _d in [os.getcwd(), os.path.join(os.getcwd(), "products", "rearc")]:
        _c = os.path.join(_d, "spark", "python", "src")
        if os.path.isdir(_c):
            _ETL_SRC = _c
            break
if _ETL_SRC and _ETL_SRC not in sys.path:
    sys.path.insert(0, _ETL_SRC)

# No default_cluster: brickflow 1.6+ uses serverless compute (required for serverless-only workspaces)
wf = Workflow(
    "rearc_quest_workflow",
    schedule_quartz_expression="0 0/20 0 ? * * *",
    tags={
        "product_id": "rearc",
    },
    permissions=WorkflowPermissions(
        can_manage_run=[User("krishnaveni.nkatte@gmail.com")],
        can_manage=[User("krishnaveni.nkatte@gmail.com")]
    ),
    default_task_settings=TaskSettings(
        email_notifications=EmailNotifications(
            on_start=["krishnaveni.nkatte@gmail.com"],
            on_success=["krishnaveni.nkatte@gmail.com"],
            on_failure=["krishnaveni.nkatte@gmail.com"],
        )
    ),
)

@wf.task
def start():
    pass

@wf.task(depends_on=start)
def bls_sync():
    import etl.bls_sync  

@wf.task(depends_on=start)
def datausa_population_sync():
    import etl.datausa_population_sync 

@wf.notebook_task(depends_on=[bls_sync, datausa_population_sync])
def load_bronze_layer():
    return NotebookTask(
        notebook_path="spark/python/src/notebooks/load_bronze_layer.ipynb",
    )

@wf.notebook_task(depends_on=load_bronze_layer)
def load_silver_layer():
    return NotebookTask(
        notebook_path="spark/python/src/notebooks/load_silver_layer.ipynb",
    )


@wf.notebook_task(depends_on=load_silver_layer)
def data_analysis():
    return NotebookTask(
        notebook_path="spark/python/src/notebooks/data_analysis_gold_layer.ipynb",
    )


@wf.task(depends_on=data_analysis)
def end():
    pass
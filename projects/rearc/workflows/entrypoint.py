# Databricks notebook source

import brickflow
from brickflow import Project
import workflows


def main() -> None:
    with Project(
        "rearc",
        git_repo="https://github.com/Krishnaveni-bannurkar/rearc.git",
        provider="github",
    ) as f:
        f.add_pkg(workflows)


if __name__ == "__main__":
    main()
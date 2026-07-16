"""
Shared pytest fixtures for PySpark unit tests.

A single local SparkSession is created once per test session (not per test)
since SparkSession creation is relatively expensive. Reusing it across
tests keeps it fast. 
"""

import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    spark = (
        SparkSession.builder
        .master("local[1]") # run locally with 1 thread/core
        .appName("bronze-unit-tests")
        .config("spark.sql.shuffle.partitions", "1")  # keep everything in single partition to keep small tests fast
        .getOrCreate()
    )
    yield spark
    spark.stop()
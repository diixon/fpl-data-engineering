# I use the Python 3.11 version of the official Airflow image, not the default 3.8.
# Why: The psycopg v3 library (which I use for Postgres connections) requires 
# Python 3.9 or newer. Using 3.8 would cause a ModuleNotFoundError at runtime.
FROM apache/airflow:2.8.1-python3.11

# I switch to the 'airflow' user before installing packages.
# Why: If I run pip install as root, the packages are saved in a root-owned 
# directory that the Airflow scheduler cannot read. Running as the airflow 
# user ensures the packages land in the correct local site-packages folder.
USER airflow

# I copy requirements.txt first, then install. This is a standard Docker caching 
# pattern: if I only change my Python code later, Docker won't re-run pip install.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
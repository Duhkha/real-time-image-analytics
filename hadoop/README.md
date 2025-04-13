# Hadoop MapReduce Setup and Execution (Requirement 3 - Custom Cluster)

This document describes the setup and execution of a Hadoop MapReduce job for processing image metadata, specifically counting detected object occurrences. This implementation uses a custom Hadoop cluster running in a Docker container and reads/writes data from/to Hetzner S3, fulfilling the core requirements of Requirement 3 of the project.

## Project Goal (Hadoop Part)

The goal of this MapReduce job is to:

1.  Read OpenCV-generated JSON metadata (containing object detection results) from a specified Hetzner S3 bucket prefix.
2.  Process this data using Hadoop MapReduce to aggregate and count the occurrences of each detected object category (label).
3.  Write the final aggregated counts (label and total count) back to a specified Hetzner S3 bucket prefix.

## Hadoop Cluster Details

* **Hadoop Cluster Hostname:** `hadoop.spacerra.com`
* **Infrastructure:** Hadoop runs inside a Docker container on a host machine.
* **Host Machine Access:** `ssh root@91.107.224.205`
* **Docker Container Access:** `docker exec -it spacerra-stack-hadoop-1 bash` (or `docker exec -it 6f789791ad6e bash`)
* **Hadoop Version:** 3.2.1 (running inside the container)

## Data Location

* **Input Data:** OpenCV metadata files (JSON format, one JSON object per line) are read from Hetzner S3 at the following prefix:
    * `s3a://2025-group19/metadata/`
* **Output Data:** Aggregated object counts are written to Hetzner S3 at the following prefix:
    * `s3a://2025-group19/mapreduce-output/object-counts/`
    * The output data is in text format, with each line containing `label<TAB>count` (e.g., `car\t123`, `person\t45`). Output files will be named like `part-r-00000`, `part-r-00001`, etc.

## MapReduce Scripts

The MapReduce job is implemented using two Python 3 scripts with Hadoop Streaming:

* **`mapper.py`**:
    * Reads JSON metadata records from standard input (one JSON object per line).
    * Extracts the object labels from the `"detections"` list within each JSON record.
    * Emits key-value pairs to standard output in the format `label<TAB>1` for each detected object instance.
* **`reducer.py`**:
    * Reads sorted `label<TAB>1` pairs from standard input (grouped by label).
    * Aggregates the counts for each unique label.
    * Writes the final aggregated counts to standard output in the format `label<TAB>total_count`.
* **Location & Permissions:** The scripts must reside inside the Hadoop container (e.g., at `/mapper.py` and `/reducer.py`) and must be made executable (`chmod +x /mapper.py /reducer.py`).

## Key Configuration (Inside Hadoop Container)

To enable Hadoop to access data in Hetzner S3 and execute the Python scripts, the following configuration was performed within the Docker container:

### 1. Hadoop S3A Configuration

* The `core-site.xml` file was modified to include Hetzner S3 credentials and endpoint details.
* **File Location:** `/opt/hadoop-3.2.1/etc/hadoop/core-site.xml`
* **Properties Added:**
    ```xml
    <property>
      <name>fs.s3a.access.key</name>
      <value>YOUR_HETZNER_S3_ACCESS_KEY</value> </property>
    <property>
      <name>fs.s3a.secret.key</name>
      <value>YOUR_HETZNER_S3_SECRET_KEY</value> </property>
    <property>
      <name>fs.s3a.endpoint</name>
      <value>YOUR_HETZNER_S3_ENDPOINT</value> </property>
    <property>
      <name>fs.s3a.path.style.access</name>
      <value>true</value>
    </property>
    <property>
      <name>fs.s3a.impl</name>
      <value>org.apache.hadoop.fs.s3a.S3AFileSystem</value>
    </property>
    <property>
        <name>fs.AbstractFileSystem.s3a.impl</name>
        <value>org.apache.hadoop.fs.s3a.S3A</value>
    </property>
    ```
* **Editing Workaround:** Due to potential issues with package managers (`apt-get`) inside the container preventing the installation of text editors like `nano`, the `core-site.xml` file was copied from the container to the host machine (`docker cp ...`), edited on the host, and then copied back into the container (`docker cp ...`).

### 2. Hadoop Classpath for S3A

* **Problem:** Hadoop initially threw a `ClassNotFoundException` for `org.apache.hadoop.fs.s3a.S3AFileSystem` because the necessary JARs (especially `hadoop-aws-3.2.1.jar`) were not on the default classpath used by the `hadoop` command.
* **JAR Location:** `/opt/hadoop-3.2.1/share/hadoop/tools/lib/`
* **Solution (Temporary/Per-Session):** Before running `hadoop fs` or `hadoop jar` commands requiring S3 access, set the `HADOOP_CLASSPATH` environment variable in the container's shell session:
    ```bash
    export HADOOP_CLASSPATH=$(hadoop classpath):/opt/hadoop-3.2.1/share/hadoop/tools/lib/*
    ```
* **Solution (Permanent - Recommended):** Add the `export HADOOP_CLASSPATH=...` line above to the Hadoop environment setup script: `/opt/hadoop-3.2.1/etc/hadoop/hadoop-env.sh`.

## Steps to Run the MapReduce Job

1.  **Access the Container:**
    ```bash
    # On the host machine (91.107.224.205)
    docker exec -it spacerra-stack-hadoop-1 bash
    ```
2.  **Set Classpath (if not permanently set):**
    ```bash
    # Inside the container
    export HADOOP_CLASSPATH=$(hadoop classpath):/opt/hadoop-3.2.1/share/hadoop/tools/lib/*
    ```
3.  **Verify S3 Access (Optional but recommended):**
    ```bash
    # Inside the container
    hadoop fs -ls s3a://2025-group19/
    hadoop fs -ls s3a://2025-group19/metadata/
    ```
    * This should list the contents if configuration and classpath are correct. Ensure the input path exists and the output path *does not* exist before running the job.
4.  **Ensure Scripts Exist and are Executable:**
    * Verify `/mapper.py` and `/reducer.py` are present in the container.
    * If needed, copy them using `docker cp` from the host.
    * Make them executable: `chmod +x /mapper.py /reducer.py`.
5.  **Define Job Variables (Optional, for clarity):**
    ```bash
    # Inside the container
    STREAMING_JAR="/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar"
    INPUT_PATH="s3a://2025-group19/metadata/"
    OUTPUT_PATH="s3a://2025-group19/mapreduce-output/object-counts/"
    MAPPER_SCRIPT="/mapper.py"
    REDUCER_SCRIPT="/reducer.py"
    PYTHON_EXE="/usr/bin/python3" 
    ```
6.  **Execute the Hadoop Streaming Job:**
    ```bash
    # Inside the container
    hadoop jar $STREAMING_JAR \
        -D mapreduce.job.name="Object Count from S3 (Py3.5 Compat)" \
        -D mapreduce.job.reduces=3 \
        -D mapreduce.map.memory.mb=1536 \
        -D mapreduce.map.java.opts=-Xmx1024m \
        -files $MAPPER_SCRIPT,$REDUCER_SCRIPT \
        -mapper "$PYTHON_EXE $MAPPER_SCRIPT" \
        -reducer "$PYTHON_EXE $REDUCER_SCRIPT" \
        -input $INPUT_PATH \
        -output $OUTPUT_PATH
    ```
    * **Note:** The `-D` flags configure job properties like the name, number of reducers, and memory settings. `-files` ensures the scripts are distributed to worker nodes.
7.  **Monitor Job Progress:** Observe the command line output for job status updates (map and reduce progress).
8.  **Check Output After Completion:**
    ```bash
    # Inside the container
    # List the output files created in S3
    hadoop fs -ls s3a://2025-group19/mapreduce-output/object-counts/

    # View the contents of one of the output files
    hadoop fs -cat s3a://2025-group19/mapreduce-output/object-counts/part-r-00000
    ```

## Troubleshooting Notes

Common issues encountered during setup and execution:

* **JSON Parsing Error:** Initial failures occurred if input JSON data spanned multiple lines or had indentation.
    * **Solution:** Ensure each JSON record in the S3 input path is stored on a single line.
* **`ClassNotFoundException` for `S3AFileSystem`:** Hadoop couldn't find the necessary class to interact with S3.
    * **Solution:** Correctly set the `HADOOP_CLASSPATH` environment variable to include the path containing `hadoop-aws-*.jar` (`/opt/hadoop-3.2.1/share/hadoop/tools/lib/*`), either per-session or permanently in `hadoop-env.sh`.
* **`python3: No such file or directory`:** Hadoop Streaming couldn't find the Python interpreter specified in the `-mapper`/`-reducer` commands.
    * **Solution:** Use the absolute path to the `python3` executable (e.g., `/usr/bin/python3`) instead of relying on the system's PATH variable within the Hadoop task environment.
* **`SyntaxError: invalid syntax` in Python Scripts:** Scripts using newer Python features (like f-strings, introduced in Python 3.6) failed if the Hadoop tasks executed them with an older Python version (e.g., Python 3.5).
    * **Solution:** Modify the scripts to use syntax compatible with the Python version available to Hadoop tasks (e.g., use `.format()` instead of f-strings).
* **File Editing Difficulties:** Editing configuration files like `core-site.xml` directly inside the container can be hard if standard editors aren't installed.
    * **Solution:** Use `docker cp` to copy files between the host and container for editing.
* **Line Endings:** Files copied from Windows systems might have incorrect line endings (`\r\n` instead of `\n`).
    * **Solution:** Use tools like `dos2unix` or `sed` (e.g., `sed -i 's/\r$//' script.py`) inside the container to fix line endings if scripts fail unexpectedly.

## Tools Used

* Apache Hadoop 3.2.1
* Hadoop Streaming
* Python 3 (including standard libraries like `json`, `sys`)
* Hetzner S3 (as the storage backend)
* Docker
* `ssh` (for host access)
* `docker exec` (for container access)
* `docker cp` (for file transfer between host and container)
* `hadoop fs` (for HDFS/S3 file operations)
* `hadoop jar` (for running MapReduce jobs)
* `chmod` (for setting script permissions)
* Standard Linux command-line tools (`export`, `ls`, `cat`, etc.)
* Text editors (`nano`, `vi`, or editors on the host machine)
* `sed` or `dos2unix` (potentially for fixing line endings)
* `boto3` (Python library, mentioned for initial S3 access checks, though not directly used by the MapReduce job itself)
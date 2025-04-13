# Hadoop MapReduce Setup and Execution

This document describes the setup and execution of a Hadoop MapReduce job for processing image metadata, as part of a larger image analytics pipeline. This implementation fulfills the core requirements of Requirement 3 of the project, using a custom Hadoop cluster.

## Project Goal (Hadoop Part)

The goal of this MapReduce job is to:

* Read OpenCV-generated metadata (object detection results) from Hetzner S3.
* Aggregate the data to count the number of occurrences of each detected object category.
* Write the aggregated counts to Hetzner S3.

## Hadoop Cluster Details

* Hadoop cluster is running on a custom infrastructure at `hadoop.spacerra.com`.
* Hadoop is running inside a Docker container on the host machine.
* Hadoop version: 3.2.1

## Data Location

* **Input Data:** OpenCV metadata files (JSON format) are read from Hetzner S3 at the following prefix:
    * `s3a://2025-group19/metadata/`
* **Output Data:** Aggregated object counts are written to Hetzner S3 at the following prefix:
    * `s3a://2025-group19/mapreduce-output/object-counts/`
    * The output data is in text format, with each line containing `label<TAB>count` (e.g., `car\t123`, `person\t45`).

## MapReduce Scripts

The MapReduce job is implemented using two Python 3 scripts with Hadoop Streaming:

* `mapper.py`:
    * Reads JSON metadata records from standard input (one JSON object per line).
    * Extracts the object labels from the `"detections"` list in each JSON record.
    * Emits key-value pairs to standard output in the format `label<TAB>1` for each detected object.
* `reducer.py`:
    * Reads sorted `label<TAB>1` pairs from standard input.
    * Aggregates the counts for each unique label.
    * Writes the final aggregated counts to standard output in the format `label<TAB>total_count`.

## Key Configuration

To enable Hadoop to access data in Hetzner S3 and execute the Python scripts, the following configuration was performed:

* **Hadoop S3A Configuration:** The `core-site.xml` file inside the Hadoop container was modified to include Hetzner S3 credentials and endpoint:
    ```xml
    <property>
      <name>fs.s3a.access.key</name>
      <value>YOUR_HETZNER_S3_ACCESS_KEY</value>
    </property>
    <property>
      <name>fs.s3a.secret.key</name>
      <value>YOUR_HETZNER_S3_SECRET_KEY</value>
    </property>
    <property>
      <name>fs.s3a.endpoint</name>
      <value>[https://your-region.s3.your-storagebox.de](https://your-region.s3.your-storagebox.de)</value>  </property>
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
* **Hadoop Classpath:** The `HADOOP_CLASSPATH` environment variable was set to include the Hadoop AWS JARs, which provide the `S3AFileSystem` class. This was done either by adding an `export` command to the shell session or by modifying the `hadoop-env.sh` script inside the container.

## Steps to Run the MapReduce Job (Simplified)

Assuming you have access to the Hadoop cluster and the necessary credentials, the basic steps to run the object counting job are:

1.  Ensure the `mapper.py` and `reducer.py` scripts are present in the Hadoop container's filesystem.
2.  Set the `HADOOP_CLASSPATH` environment variable to include the Hadoop AWS JARs (if not already configured permanently).
3.  Execute the `hadoop jar` command with the correct paths to the streaming JAR and the scripts, and the input/output paths in S3:

    ```bash
    hadoop jar /path/to/hadoop-streaming-3.2.1.jar \
        -D mapreduce.job.name="Object Count from S3" \
        -D mapreduce.job.reduces=3 \
        -D mapreduce.map.memory.mb=1536 \
        -D mapreduce.map.java.opts=-Xmx1024m \
        -files /mapper.py,/reducer.py \
        -mapper "/usr/bin/python3 /mapper.py" \
        -reducer "/usr/bin/python3 /reducer.py" \
        -input s3a://2025-group19/metadata/ \
        -output s3a://2025-group19/mapreduce-output/object-counts/
    ```

## Troubleshooting

The following issues were encountered and resolved during the setup and execution of the MapReduce job:

* **JSON Parsing Error:** The initial mapper script failed due to the input JSON data being formatted with multiple lines and indentation. The solution was to ensure that each JSON record in S3 was stored on a single line.
* **`ClassNotFoundException` for `S3AFileSystem`:** The Hadoop framework could not find the `S3AFileSystem` class, which is needed to access data in S3. This was resolved by adding the Hadoop AWS JARs directory to the `HADOOP_CLASSPATH`.
* **`python3: No such file or directory`:** The Hadoop Streaming job could not find the Python 3 interpreter. This was resolved by using the absolute path to the `python3` executable (e.g., `/usr/bin/python3`) in the `-mapper` and `-reducer` arguments of the `hadoop jar` command, instead of relying on the system's `PATH`.
* **`SyntaxError: invalid syntax`:** The Python scripts contained f-strings (Python 3.6+ syntax), but the Hadoop tasks were running the scripts with an older Python version (likely Python 3.5). The scripts were modified to use `.format()` instead, which is compatible with Python 3.5.

## Tools Used

* Apache Hadoop 3.2.1
* Hadoop Streaming
* Python 3
* `boto3` (for initial S3 access check)
* Docker
* `docker cp`
* `ssh`
* `hadoop jar`
* `sed` (for fixing file line endings)
* `nano` / `vi` (for editing configuration files)
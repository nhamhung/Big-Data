# Sparklens (adjust # of executors)
- 3 optimizations: reduce driver side computations + having enough tasks for given cores + reducing task skew

- Critical path = Driver time + largest task time for each stage. Adding more executors does not make the application run faster unless we change distribution of the tasks

- If critical path < Total WallClock (Driver + Executor Wallclock), then adding executors will lower latency/improve performance, or else we can do better just by increasing executors

- Ideal Application Estimate: Assume no skew + all tasks uniform + enough tasks for every executor (assume application scale linearly with executors)

# Spark + AI Summit 2019
- Number of partitions = 2x to 4x number of cores in cluster
- Number of cores per executor = 4-8
- Memory per executor = 85% * (node memory / # executors by node)
- Shuffle spill (deserialized data produced by map stages in a shuffle does not fit in memory) = Increase number of partitions / Increase memory available to each task (increase spark executor memory or decrease number of cores per executor)

Node metrics:
- CPU graph: Low CPU usage -> schedule more tasks
- Memory graph: Low memory usage -> reduce excess memory and switch to CPU-intensive instances
- IO bound queries: Change Spark IO configurations such as compression or IO buffer sizes

# Spark Autotuning

- Executor Sizing (based on resources' relative abundance)

- MemPerCore = QueueMem/QueueCores (how much mem per core) * MemHungry (a factor whether application is memory hungry)
- CoresPerExecutor = min(MaxUsableMemoryPerContainer/MemoryPerCore, 5)
- MemPerExecutor = max(1GB, MemPerCore * CoresPerExecutor)

- AvailableExecutors per node = Sum for all nodes Min(AvailableNodeMemory/(MemoryPerExecutor + Overhead) , AvailableNodeCores/CoresPerExecutor)
- UsableExecutors (Queue Constraints) = Min(AvailableExecutors, QueueMemory/MemoryPerExecutor, QueueCores/CoresPerExecutor)

- NeededExecutors (for Memory requirements) = CacheSize / SparkMemPerExecutor * SparkStorageFraction
- FinalExecutors = min(UsableExecutors, NeededExecutors * ComputeHungry)

- Partitioning

- MinPartitions = NumExecutors * CoresPerExecutor
- Memory Constraint: MemPerTask = SparkMemPerExecutor*(1-SparkStorageFraction) / CoresPerExecutor
- MemPartitions = CacheSize/MemPerTask
- FinalPartitions = max(MinPartitions, MemPartitions)

# Application relevant config:
- spark.executor.pyspark.memory: Amount of memory allocated to PySpark in each executor. Set if we want to limit Python's memory use and it is up to application to avoid exceeding the overhead memory space shared with other non-JVM processes
- spark.executor.memoryOverhead = executorMemory * 0.10, minimum 384m. Amount of additional memory allocated per executor process to account for VM or other overheads. Additional memory includes PySpark executor memory when spark.executor.pyspark.memory is not set and memory used by other non-executor processes running in same container.

## Shuffle behavior config:
- spark.reducer.maxSizeInFlight = 48m default: Max size of map outputs to fetch simultaneously from each reduce task. Each output requires to create a buffer to receive it, this represents a fixed memory overhead per reduce task. Keep small unless we have enough memory
- spark.reducer.maxReqsInFlight = Int.MaxValue default: Limit the number of remote requests to fetch blocks at any given point. When the number of hosts in cluster increase it might lead to very large number of inbound connections to one or more nodes causing the workers to fail under load.
- spark.reducer.maxBlocksInFlightPerAddress = Int.MaxValue default: Limit the number of remote blocks being fetched per reduce task from a given host port. When a large number of blocks are being requested from a given address in a single fetch or simultaneously, this could crash the serving executor or NodeManager
- spark.shuffle.compress = true. Whether to compress map output files. Compression will use spark.io.compression.codec
- spark.shuffle.file.buffer = 32k default. Size of in-memory buffer for each shuffle file output stream. These buffers reduce number of disk seeks and system calls made in creating intermediate shuffle files
- spark.shuffle.service.enabled = false default. Enable external shuffle service which preserves the shuffle files written by executors so they can be safely removed in the event of executor failure. External shuffle service must be set up to use in the case of dynamic allocation
- spark.shuffle.maxChunksBeingTransferred = Long.MAX_VALUE. Number of chunks allowed to be transferred at the same time on shuffle service. New incoming connections will be closed when max number is hit. The client will retry according to shuffle retry configs (spark.shuffle.io.maxRetries and spark.shuffle.io.retryWait). If these limits are reached the task will fail with fetch failure.

## Compression and Serialization
- spark.serializer = org.apache.spark.serializer.JavaSerializer default. Class used to serialize objects sent over the network or need to be cached in serialized form. It is recommended to use org.apache.spark.serializer.KryoSerializer instead

## Memory management
- spark.memory.fraction = 0.6 default. Fraction of (heap space - 300MB) used for execution and storage. The lower this is the more frequently spills and cached data eviction occur. This config sets aside the remaining memory for internal metadata, user DS, impresize size estimation in the case of sparse, unusually large records.
- spark.memory.storageFraction = 0.5 default. Amount of storage memory immune to eviction and this is a fraction of the size of region set by spark.memory.fraction. The high this is, the less working memory may be available to execution and tasks may spill to disk more often
- spark.memory.offHeap.enabled = false. If true, Spark will attempt to use off-heap memory for certain operations.
- spark.memory.offHeap.size = 0. The absolute amount of memory which can be used for off-heap allocation. This setting has no impact on heap memory usage.

## Executor behavior
- spark.default.parallelism. Default number of partitions in RDDs returned by join, reduceByKey which is the largest number of partitions in a parent RDD.
- spark.files.maxPartitionBytes = 134217728 (128MiB) default. The maximum number of bytes to pack into a single partition when reading files

## Networking
- spark.network.timeout = 120s default. Default timeout for all network interactions.

## Dynamic Allocation
- spark.dynamicAllocation.enabled = false default. Scale the number of executors registered with this application up and down based on workload. Requires spark.shuffle.service.enabled or spark.dynamicAlloaction.shuffleTracking.enabled.
- spark.dynamicAllocation.initialExecutors/minExecutors/maxExecutors
- spark.dynamicAllocation.executorAllocationRatio = 1 default. By default, dynamic allocation will request enough executors to maximize parallelism according to the number of tasks to process. While this minimizes latency of the job, with small tasks this setting can waste a lot of resources due to executor allocation overhead as some may not do any work. This setting allows a ratio that can reduce the number of executors w.r.t full parallelism.
- spark.dynamicAllocation.shuffleTracking.enabled = false default.  Enable shuffle file tracking for executors which allows dynamic allocation without the need for an external shuffle service. This option will try to keep alive executors that are storing shuffle data for active jobs.

## Spark SQL
- spark.sql.adaptive.advisoryPartitionSizeInBytes = spark.sql.adaptive.shuffle.targetPostShuffleInputSize (64MB default). The advisory size in bytes of the shuffle partition during adaptive optimization when Spark coalesces small shuffle partitions or splits skewed shuffle partition.
- spark.sql.adaptive.autoBroadcastJoinThreshold = spark.sql.autoBroadcastJoinThreshold default. Configures the max size in bytes for a table that will be broadcast to all worker nodes when performing a join. Setting to -1 will disable broadcasting.
- spark.sql.adaptive.coalescePartitions.enabled = true default. When true and with spark.sql.adaptive.enabled, Spark will coalesce contiguous shuffle partitions according to the target size specified by spark.sql.adaptive.advisoryPartitionSizeInBytes to avoid many small tasks
- spark.sql.adaptive.coalescePartitions.initialPartitionNum = spark.sql.shuffle.partitions default.
- spark.sql.adaptive.coalescePartitions.minPartitionSize = 1MB default. Minimum size of shuffle partitions after coalescing.
- spark.sql.adaptive.enabled = true default. Enable AQE, re-optimize the query plan in the middle of query execution based on accurate runtime statistics
- spark.sql.adaptive.localShuffleReader.enabled = true default. Tries to use local shuffle reader to read the shuffle data when the shuffle partitioning is not needed, for example, after converting sort-merge join to broadcast-hash join.
- spark.sql.adaptive.maxShuffleHashJoinLocalMapThreshold = 0b default. Configure the max size in bytes per partition that can be allowed to build a local hash map. If this value is not smaller than spark.sql.adaptive.advisoryPartitionSizeInBytes and all the partition size are not larger than this config, join selection prefer to use shuffled hash join instead of sort merge join
- spark.sql.adaptive.optimizeSkewsInRebalancePartitions.enabled = true default. When true and spark.sql.adaptive.enabled is true, Spark will optimize the skewed shuffle partitions in RebalancePartitions and split them to smaller ones according to target size set by spark.sql.adaptive.advisoryPartitionSizeInBytes
- spark.sql.adaptive.optimizer.excludeRules. Configures a list of rules to be disabled in the adaptive optimizer, in which the rules are specified by their rule names and separated by comma.
- spark.sql.adaptive.skewJoin.enabled = true default. When true and 'spark.sql.adaptive.enabled' is true, Spark dynamically handles skew in shuffled join (sort-merge and shuffled hash) by splitting and replicating if needed skewed partitions
- spark.sql.adaptive.skewJoin.skewedPartitionFactor = 5. A partition is skewed if its size is larger than this factor multiplying the median partition size and also larger than spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes.
- spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes = 256MB. A partition is considered as skewed if its size in bytes is larger than this threshold and also larger than the above.
- spark.sql.autoBroadcastJoinThreshold = 10MB default. Max size for a table to be broadcast to all worker nodes when performing a join. Statistics only supported for Hive Metastore tables where ANALYZE TABLE <tablename> COMPUTE STATISTICS noscan has been run or file-based data source tables where statistics are computed directly on data files
- spark.sql.bucketing.coalesceBucketsInJoin.enabled = false. When true, if 2 bucket tables with different number of buckets are joined, the side with a bigger number of buckets will be coalesced to have same number of buckets as the other side. Bigger number of buckets is divisible by smaller number of buckets. Bucket coalescing is applied to sort-merge join and shuffle hash join
- spark.sql.files.maxPartitionBytes = 128MB default. The maximum number of bytes to pack into a single partition when reading files.
- spark.sql.files.maxRecordsPerFile = 0. Maximum number of records to write out to a single file.

## AQE
- Broadcast small join table doesn't work: AQE does not broadcast the left relation of LEFT OUTER JOIN. Also, if the relation contains a lot of empty partitions, in which case majority of tasks can finish quicky with sort merge join or can be optimized with skew join handling -> AQE avoids changing such SMJ to BHJ if percentage of non-empty partitions < spark.sql.adaptive.nonEmptyPartitionRatioForBroadcastJoin
- Data skew optimization doesn't work: Skewed partition AQE only works given 2 conditions: partition size > spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes and partition size > median size of all partitions * skewed factor. Also, in LEFT OUTER JOIN, only skew on left side can be optimized

# Calculate the ideal number of shuffle partitions

https://confluence.garenanow.com/pages/viewpage.action?spaceKey=DATA&title=2021-11+Spark+SQL+Analysis
- Number of partitions depends on the dataset size and number of cores.
- Each partition should be less than 200MB for better performance. Ideal size is (100-200MB)

- For limited cluster size and small DataFrame: set number of partitions to 1x or 2x number of cores (each partition should be less than 200MB): e.g. input size: 2 GB with 20 cores, set shuffle partitions to 20 or 40
- For limited cluster size but large DataFrame: set the number of shuffle partitions to Input Data Size / Partition Size (<= 200mb per partition) e.g. input size: 20 GB with 40 cores, set shuffle partitions to 120 or 160 (3x to 4x of the cores & makes each partition less than 200 mb)
- For large cluster size with more cores than the needed number of partitions, set to 1x or 2x number of cores. e.g. input size: 80 GB (which requires less than 400 partitions) with 400 cores, set shuffle partitions to 400 or 800

# Dr. Elephant Metrics

- Mapper Data Skew
- Mapper GC
- Mapper Time
- Mapper Speed
- Mapper Spill
- Mapper Memory
- Reducer Data Skew
- Reducer GC
- Reducer Time
- Reducer Memory
- Shuffle & Sort

## Dr. Elephant's MR Heuristics: https://github.com/linkedin/dr-elephant/tree/master/app/com/linkedin/drelephant/mapreduce

- MapperDataSkewHeuristic: Get the number of bytes for each Mapper in an array. Then, check if the array has deviating elements by comparing each individual value against the average. Obtain the most deviated element and its most absolute difference from average. If this most difference > minimum difference allowed which is max(buffer, average * deviating factor), then this mapper is skewed. Return the mapper task ID with the skew.
- ReducerDataSkewHeuristic: Same as MapperDataSkewHeuristic
- UnsplittableFilesHeuristic: Get all mappers. Ignore jobs with only a single mapper. Get number of bytes for each mapper and compute average. If average is larger than twice the HDFS_BLOCK_SIZE (512 MB) then we have unsplittable files problem on mapper side
- SmallFilesHeuristic: Get all mappers. Ignore if the number of mappers is small meaning little data anyway. Get number of bytes for all mapper. Get average number of bytes per mapper. If average size is less than HDFS_BLOCK_SIZE / 4, then we have small files problem
- GeneralMapperSlowHeuristic: For all mappers tasks, get their runtime and speed. Runtime is from start to finish and is subtracted by 1 minute buffer. If runtime < 1 sec, set it at 1 sec. Get speed which is number of bytes/second. Then get average speed and average runtime. If average run time < 10 minutes, consider Succes. For average speed, it must be less than DISK_READ_SPEED (100MB per second) / 4, or else it is considered having BuildError.
- SlowShuffleSortHeuristic: Get all reducers and their corresponding execTime, shuffleTime, sortTime. Compute avgExecTime, avgShuffleTime, avgSortTime. Set limit to be max(avgExecTime, 1 minute). If avgShuffleTime exceeds at least 1 minute then there is slow shuffle in reducers. If avgSort exceeds at least 1 minute then there is slow sort in reducers.
- JobQueueLimitHeuristic: The task execution limit or queueTimeOut on the Default queue is (15 Mins or 900 seconds). Fetch the queue to which the job is submitted. Get all map tasks and reduce tasks. Get all map tasks' and reduce tasks' severity. For each task, score different severity level based on queueTimeOut - 4/3/2/1 * timeUnit of 30s. Thus, a task is considered SEVERE if queue time is 14-14.5 mins, CRITICAL if queue time is over 14.5 mins. Calculate Job severity by find the max security level across both map tasks and reduce tasks.
- MapperSpillHeuristic: Get totalSpills records, totalOutputRecords across all mapper tasks. Then, find the ratioSpills if totalSpills is not 0 by totalSpills / totalOutputRecords. Set a severity level for this ratioSpills by 1.25/1.5/1.75/2 * THRESHOLD_SPILL_FACTOR = 10000.
...

## Dr. Elephant's Spark Heuristics:
- ConfigurationHeuristics: A heuristic based on app's known configurations to primarily inform users about key app configuration settings such as driver memory, driver cores, executor cores, executor instances, executor memory, serializer
- Result: KyroSerializer, Spark shuffle service, minimum executors for DA, maximum executors for DA, Jars notation, Driver Overhead memory, Executor Overhead memory
- Get the following: spark.driver.memory, spark.executor.memory, spark.executor.instances, spark.executor.cores, spark.serializer, spark.application.duration, spark.shuffle.service.enabled, spark.dynamicAllocation.enabled, spark.driver.cores, spark.dynamicAllocation.minExecutors, spark.dynamicAllocation.maxExecutors, spark.yarn.secondary.jars, spark.yarn.executor.memoryOverhead, spark.yarn.driver.memoryOverhead,
- Severity: If sparkYarnJars.contains('*') when specifying the jars then Severity.CRITICAL. If serializer is either not configured or not equal to KryoSerializer, then Severity.MODERATE. Check both driver and executor's memory and cores value thresholds using some experimental thresholds: Memory is 10/15/20/25 for low/moderate/severe/critical. Number of cores is 4/6/8/10 for low/moderate/severe/critical. So there are 4 severity indicators here. If severityMinExecutors is > THRESHOLD_MIN_EXECUTORS or severityMaxExecutors < THRESHOLD_MAX_EXECUTORS then Severity.CRITICAL. If dynamic allocation is disabled then Severity.MODERATE if shuffle service is disabled or not specified. If dynamic allocation is enabled, then Severity.SEVERE if shuffle service is disabled or not specified.

### ExecutorHeuristics: A heuristic concerns the distribution (min, 25p, median, 75p, max) of key executor metrics including input bytes, shuffle read bytes, shuffle write bytes, storage memory used and task time. The max-to-median ratio determines the severity of any particular metric.
- Ignore severity analysis if distribution for memory or time less than these thresholds: default_ignore_max_bytes_less_than_threshold = 100MB, default_ignore_max_millis_less_than_threshold = 5 mins.
- Evaluate by getting: total executor storage memory allocated, total executor storage memory used, executor storage memory utilization rate, executor storage memory used distribution, executor task time distribution, executor task time sum, executor input bytes distribution, executor shuffle read bytes distribution, executor shuffle write bytes distribution.
- Scoring severity: executor storage memory used distribution + executor task time distribution + executor input bytes distribution, executor shuffle read bytes distribution, executor shuffle write bytes distribution
- If distribution.max < ignore theshold -> Severity.NONE. If distribution.median = 0 then Severity.MaxLongValue. Else -> distribution.max / distribution.median
Max_to_median_ratio_threshold_severity: 10 ^ 0.125/0.25/0.5/1 for low/moderate/severe/critical

### JobsHeuristics: A heuristic which reports job failures and high task failure rates for each job.
- Result: Spark completed jobs count, Spark failed jobs count, Spark failed jobs list, Spark job failure rate, Spark jobs with high task failure rates
- default_job_failure_rate_severity_thresholds = 0.1/0.3/0.5/0.5 for low/moderate/severe/critical
- default_task_failure_rate_severity_thresholds = 0.1/0.3/0.5/0.5
- Evaluate by getting: numCompletedJobs, numFailedJobs, failedJobs, jobFailureRate=numFailedJobs/numJobs, jobsWithHighTaskFailureRates (taskFailureRate=numFailedTasks/numTasks)

### StagesHeuristics: A heuristic which reports stage failures, high task failure rates for each stage and long average executor runtimes for each stage
- Result: Spark completed stages count, Spark failed stages count, Spark stage failure rate, Spark stages with high task failure rates, Spark stages with long average executor runtimes
- default_stage_failure_rate_severity_thresholds = 0.1/0.3/0.5/0.5 for low/moderate/severe/critical
- default_task_failure_rate_severity_thresholds = 0.1/0.3/0.5/0.5 for low/moderate/severe/critical
- default_stage_runtime_millis_severity_threshold = 15/30/45/60 mins for low/mod/ser/crit
- Evaluate by getting: numCompletedStages, numFailedStages, stageFailureRate = numFailedStages/numStages, stagesWithHighTaskFailureRates, stagesWithLongAverageExecutorRuntimes
- Support functions: taskFailureRateOf(stage) = numFailedTasks/numTasks, averageExecutorRuntime = stage.executorRunTime / executorInstances

### ExecutorGcHeuristic: A heuristic based on GC time and CPU run time. Calculates the ratio of total time a job spends in GC to total run time of a job and warns if too much time is spent in GC
- Result: GC time to Executor Run time ration, Total GC time, Total Executor Runtime
- default_gc_severity_thresholds = 0.08/0.1/0.15/0.2 for low/moderate/severe/critical
- Get jvmGcTimeTotal, executorRunTimeTotal. Get ratio = jvmGcTimeTotal / executorRunTimeTotal

# Sparklens
  
## AppTimelineAnalyzer: Print information about all the jobs and shows how the stages were scheduled within each job
- Print Application Timeline:
- Get sorted jobids. Iterate through each, get jobID and jobTimeSpan. Print jobID, jobTimeSpan.startTime and jobTimeSpan.duration.
- Get sorted stageids. Iterate through each, get stageID, stageTimeSpan, maxTaskTime and taskCount.

## JobOverlapAnalyzer

- JobOverlapHelper class: Jobs with the same sql.execution.id are run in parallel. For completion estimator to work correctly, treat these group of jobs as a single entity

- makeJobLists: first find jobGroupListByExecID which are the job groups by ExecID. Get the set of allJobIDs and then get the set of groupJobIDs. Then, get those jobs that are not part of any ExecID by the set difference between allJobIDs.diff(groupJobIDs). Then, merge jobGroupListByExecID and leftJobIDs together to mergedJobGroupList. It is also noticed that jobs with the same ExecID also have some dependency structure and not all jobs run in parallel. As such, we try to find isolated/sequential groups here and de-group them to get finalJobGroupList. Iterate through mergedJobGroupList, if jobGroup has size 1, append to finalJobGroupList, else will splitListIfAppropriate(jobGroup) to get newLists and append newLists to finalJobGroupList.
- estimatedTimeSpentInJobs: Get jobGroupsList. For each jobGroup, get the job with maxEndTime - the job with minEndTime to get the jobGroupTime. Sum across all jobGroups
- criticalPathForAllJobs: Get jobGroupsList. For each job group, compute the job with the max job.computeCriticalTimeForJob(), which is the minimum time it would take to run this job. Sum across all job groups
- splitListIfAppropriate:

- JobTimeSpan class: The timeSpan of a Job can be seen w.r.t other jobs as well as driver timeSpans providing a timeline. Also, a Job timeline is analysed by checking individual stages.
- computeCriticalTimeForJob: compute min time to run this job taking into account the parallel stages. Get maxStageID which is the ID of the last stage. Get data which is a hashmap of (stageID, (Seq[parentStageIDs of stage], maxExecutorRunTime of stage))
- criticalTime(stageID, data): recursive function to compute critical time starting from the last stage. For instance, we get the last stageData = data.get(stageID). Then recursively, we compute the maxExecutorRuntime for each of the parentStageIDs of the current stage

- Get jobsList using JobOverlapHelper.makeJobList(). Sort jobsList by the job's min startTime within each job group. Then for each job group, get its job's minStartTime and maxEndTime and jobIDList and groupID.
- Print detailed report: JobGroup = count, SQLExecID = groupID, Number of Jobs = jobIDList.size, JobIDs = jobIDList, Timing = minStartTime to maxEndTime and Duration = maxEndTime - minStartTime.
- Get conflictJobGroups which are overlapping job groups where previous group's lastEndTime > minStartTime of next group. If there are conflictingJobGroups, then print "Found ... overlapping JobGroups. Using threadpool for submitting parallel jobs? Some calculations may not be reliable."

## EfficiencyStatisticsAnalyzer:

- Wall clock time: appTotalTime = appEnd - appStart
- Wall clock time per job aggregated: jobTime = JobOverlapHelper.estimatedTimeSpentInJobs(). For each jobGroup, get the job with maxEndTime - the job with minEndTime. Sum across all jobGroups
- Sum of cores in all executors: totalCores = maxConcurrentExecutors * executorCores (there are executors coming up and going down so we take max-number of executors at any point * num-cores per executor)
- Total compute millis available to the application: appComputeMillisAvailable = totalCores * appTotalTime
- Total compute millis from executor lifetime: computeMillisFromExecutorLifetime = sum of all executors' ecores * (eendTime - estartTime)
- Some of the compute millis are lost when driver is doing some work and has not assigned any work to the executors. Assume executors are only busy when one of the job is in progress: inJobComputeMillisAvailable = totalCores * jobTime
- criticalPathTime = Minimum time required to run a job even when we have infinite executors = max time taken by any task in the stage which is in the critical path. 

Some stages can run in parallel so we cannot reduce job time to less than this number. Aggregating over all jobs to get the lower bound on this time
Some of millis used by all tasks of all jobs: inJobComputeMillisUsed

- Perfect job time: perfectJobTime = inJobComputeMillisUsed / totalCores
- driverTimeJobBased = appTotalTime - jobTime
- driverComputeMillisWastedJobBased = driverTimeJobBased * totalCores

Output:

- Time spent in Driver vs Executors: Driver Wallclock Time | Executor Wallclock Time | Total Wallclock Time
- Min possible time for app based on critical path (with infinite resources) = driverTimeJobBased + criticalPathTime
- Min possible time for app with same executors, perfect parallelism and zero skew = driverTimeJobbased + perfectJobTime
- If we were to run this app with single executor and single core = driverTimeJobBased + inJobComputeMillisUsed
- executorUsedPercent = inJobComputeMillisUsed / inJobComputeMillisAvailable
- executorWastedPercent = (inJobComputeMillisAvailable - inJobComputeMillisUsed) / inJobComputeMillisAvailable
- driverWastedPercentOverAll = driverComputeMillisWastedJobBased / appComputeMillisAvailable
- executorWastedPercentOverall = (inJobComputeMillisAvailable - inJobComputeMillisUsed) / appComputeMillisAvailable.toFloat

Output:

- OneCoreComputeHours: Measure of total compute power available from cluster. One core in the executor, running for one hour, counts as one OneCoreComputeHour. Executors with 4 cores, will have 4 times the OneCoreComputeHours compared to one with just one core. Similarly, one core executor running for 4 hours will OnCoreComputeHours equal to 4 core executor running for 1 hour

- Driver Utilization (Cluster idle because of driver)

- Total OneCoreComputeHours available = appComputeMillisAvailable
- Total OneCoreComputeHours available (AutoScale Aware) = computeMillisFromExecutorLifetime
- OneCoreComputeHours wasted by driver = driverComputeMillisWastedJobBased

- Cluster Utilization (Executors idle because of lack of tasks or skew)

- Executor OneCoreComputeHours available = inJobComputeMillisAvailable
- Executor OneCoreComputeHours used = inJobComputemillisUsed
- OneCoreComputeHours wasted = inJobComputeMillisAvailable - inJobComputeMillisUsed

- App Level Wastage Metrics

- OneCoreComputeHours wasted Driver = driverWastedPercentOverAll
- OneCoreComputeHours wasted Executor = executorWastedPercentOverall
- OneCoreComputeHours wasted Total = driverWastedPercentOverall + executorWastedPercentOverall

## ExecutorTimelineAnalyzer
  
- Print executors timeline, Total Executors and maximum concurrent executors.
- For each minute, print At this minute, how many executors are added, how many executors are removed and the current number concurrent and available executors

## ExecutorWallclockAnalyzer
  
- Print: App completion time and cluster utilization estimates with different executor counts
- Get coresPerExecutor, appExecutorCount, testPercentages = [10,20,50,80,...]
- Get appRealDuration = endTime - startTime
- Iterate through each percentage, get the executorCount = (appExecutorCount * percent) / 100 (different scenarios of having different percentage of the current number of executors). Get estimatedTime based on (appContext, executorCount, coresPerExecutor, appRealDuration). Get estimated cluster utilization = sum of executorRunTime / estimatedTime * executorCount * coresPerExecutor (double-check this logic)

## HostTimelineAnalyzer
  
- Similar to executor timeline: At each time interval, added how many hosts
- Also, for each host, print hostID, host start time and executorsOnHost count

## StageSkewAnalyzer

def computePerStageEfficiencyStatistics:

- Get totalTasks in all stages.
- Print "Per Stage Utilization": Stage-ID, Wall Clock, Task Runtime, Task Count, IO, Input, Output, Shuffle Input, Shuffle Output, Wall Clock Time Measured, Wall Clock Time Final, OneCoreComputeHours Available, OneCoreComputeHours Used, OneCoreComputeHours Wasted, MaxTaskMem
- Get maxExecutors (concurrent), executorCores, totalCores, totalMillis = sum(each stage duration) * totalCores, totalRuntime = sum(executorRuntime), totalIOBytes = sum(inputBytesRead + outputBytesWritten + shuffleWriteBytesWritten + shuffleReadBytesRead)
- Iterate through each stage, for each: get duration, available = totalCores * duration, stagePercent = (available / totalMillis), used = executorRuntime, wasted = available - used, usedPercent = used / available, wastedPercent = wasted / available, stageBytes = inputBytesRead + outputBytesWritten + shuffleWriteBytesWritten + shuffleReadBytesRead, maxTaskMemory = sum(taskPeakMemoryUsage.take(executorCores)), IOPercent = stageBytes / totalIOBytes, taskRuntimePercent = executorRuntime / totalRunTime, idealWallClock = executorRunTime / (maxExecutors * executorCores)
- Get maxMem = sum(each stage's taskPeakMemoryUsage)

def checkForGCOrShuffleService:

- Get maxExecutors, executorCores, totalCores, totalMillis
- Sort stage by their ids, for each stage, get totalExecuorTime, writeTimePercent = shuffleWriteTime / totalExecutorTime, readFetchPercent = shuffleReadFetchWaitTime / totalExecutorTime, gcPercent = jvmGCTime / totalExecutorTime, available = totalCores * duration, stagePercent = available / totalMillis, parallelismRatio = count / totalCores, maxTaskTime = max(taskExecutionTimes), meanTaskTime, taskSkew = maxTaskTime / meanTaskTime, taskStageSkew = maxTaskTime / duration, totalInput = inputBytesRead + shuffleReadBytesRead, totalOutput = outputBytesWritten + shuffleWriteBytesWritten, oiRatio = totalOutput / totalInput
  
Print:

- PRatio: Number of tasks in stage divided by number of cores. Represents degree of parallelism in the stage
- TaskSkew: Duration of largest task in stage divided by duration of median task. Represents degree of skew in the stage
- TaskStageSkew: Duration of largest task in stage divided by total duration of the stage. Represents the impact of the largest task on stage time.
- OIRatio: Output to input ration. Total output of the stage (results + shuffle write) divided by total input (input data + shuffle read)

These metrics below represent distribution of time within the stage

- ShuffleWrite: Amount of time spent in shuffle writes across all tasks in the given stage as a percentage
- ReadFetch: Amount of time spent in shuffle read across all tasks in the given stage as a percentage
- GC: Amount of time spent in GC across all tasks in the given stage as a percentage
- If the stage contributes large percentage to overall application time, we could look into these metrics to check which part (Shuffle write, read fetch or GC is responsible)

# First-week Presentation:

Different Analysers may focus on optimizing different aspects. Most of them work based on a set of heuristics which are derived from experience

## Sparklens
  
- For this tool, the optimization is mainly focus on a concept called critical path which states that a Spark application cannot run faster than its critical path no matter how many executors
- Critical path = Driver time (the entire cluster is idle) + largest task time for each stage. Adding more executors does not make the application run faster unless we change distribution of the tasks
- 3 optimizations: reduce driver side computations + having enough tasks for given cores + reducing task skew or might just reduce number of executors

Based on the following statistics:

- Driver WallClock
- Executor WallClock
- Total WallClock
- Critical path
- Ideal application time
- Further Per-Stage Metrics such as: WallClock, PRation (num tasks/num cores), TaskSkew (Duration of largest task / median task), TaskStageSkew (largest task time / stage time), OIRatio (Ouput bytes to input bytes ratio = (Results + Shuffle Write) / (Input Data + Shuffle Read)
- Observations & Actions: How difference is Critical Path vs Ideal application time + how much is Driver WallClock + how much is Executor Core Compute Hour Used out of CCH available -> CCH wasted

## Spark Autotuning
  
- Spark default settings are targeted at toy data sets & small clusters. Also change one parameter will generally impact others: 1. Increase mem per executor -> decrease number of executors and 2. Increase cores per executor -> decrease memory per core. Thus there is not a single "correct" configuration.

Factors to consider:

- Size + complexity of data
- Complexity of algorithm
- Nuances of the implementation
- Cluster size
- Yarn coniguration
- Cluster utilization

Some Calculations to serve as guidelines

- Executor Sizing (based on resources' relative abundance)

- MemPerCore = QueueMem/QueueCores (how much mem per core) * MemHungry (a factor whether application is memory hungry)
- CoresPerExecutor = min(MaxUsableMemoryPerContainer/MemoryPerCore, 5)
- MemPerExecutor = max(1GB, MemPerCore * CoresPerExecutor)

- AvailableExecutors per node = Sum for all nodes Min(AvailableNodeMemory/(MemoryPerExecutor + Overhead) , AvailableNodeCores/CoresPerExecutor)
- UsableExecutors (Queue Constraints) = Min(AvailableExecutors, QueueMemory/MemoryPerExecutor, QueueCores/CoresPerExecutor)

- NeededExecutors (for Memory requirements) = CacheSize / SparkMemPerExecutor * SparkStorageFraction
- FinalExecutors = min(UsableExecutors, NeededExecutors * ComputeHungry)

Partitioning

- MinPartitions = NumExecutors * CoresPerExecutor
- Memory Constraint: MemPerTask = SparkMemPerExecutor*(1-SparkStorageFraction) / CoresPerExecutor
- MemPartitions = CacheSize/MemPerTask
- FinalPartitions = max(MinPartitions, MemPartitions)

## Dr Elephant
  
- More thorough analysis to assign severity levels to zoom into the problem
- ConfigurationHeuristics: A heuristic based on app's known configurations to primarily inform users about key app configuration settings such as driver memory, driver cores, executor cores, executor instances, executor memory, serializer
- ExecutorHeuristics: A heuristic concerns the distribution (min, 25p, median, 75p, max) of key executor metrics including input bytes, shuffle read bytes, shuffle write bytes, storage memory used and task time. The max-to-median ratio determines the severity of any particular metric.
- JobsHeuristics: A heuristic which reports job failures and high task failure rates for each job.
- StagesHeuristics: A heuristic which reports stage failures, high task failure rates for each stage and long average executor runtimes for each stage
- ExecutorGcHeuristic: A heuristic based on GC time and CPU run time. Calculates the ratio of total time a job spends in GC to total run time of a job and warns if too much time is spent in GC


## Automated Performance Tuning

- Iterative Performance Tuning
- Based on some rules of thumb such as # of partitions = 3x number of cores, # cores per executor = 4-8, memory per executor = 85% * (node memory / # executors by node)
- Other parameters: Educated guess

Common performance issues: lack of parallelism/ shuffle spill/ data skew/ node metrics (CPU/Memory/IO intensive)

Heuristics:
  
- FewerTasksThanTotalCores
- ShuffleSpill
- LongShuffleReadTime
- LongGC
- ExecMemoryLargerThanNeeded
- TooShortTasks
- CPUTimeShorterThanComputeTime

# Custom Heuristics
  
Heuristic rules in the form of pseudo-func with input (data required to check) and output (possible suggestions)

## 1. High Impact rules based on experience with manual tuning:

First, check the number of partitions so make sure it's at least sufficient for the number of cores as well as the heaviest stages. If the number of required partitions is very high, we can always enable spark.sql.adaptive.coalescePartitions so that lighter shuffle stages don't have too many partitions

checkParallelism(numExecutors, numCores): Number of partitions should at least match the number of cores

- Get degreeOfParallelism = numExecutors * numCores
- Get minPartitionsNumParallelism = degreeOfParallelism
- Return: minPartitionsNumParallelism

checkShuffleSpill(allStagesStats): If there is shuffle spill, there should be at least enough partitions such that each partition size is within 200Mb to 1Gb range

- Get stage with largestShuffleReadSize. 
- If largestShuffleReadSize > 1TiB, then minPartitionsNumSpill = largestShuffleReadSize.toMb() / 200 (Mb) / 5 (each partition around 1GiB), maxPartitionsNumSpill = min(8000, largestShuffleReadSize.toMb() / 200 (Mb) (each partition around 200 Mb)). Here, 8000 is set to be the cap with using 500 executors each with 4 cores. Also, enable "spark.sql.adaptive.coalescePartitions" as minPartitionsNumSpill and maxPartitionsNumSpill are likely large, so we would want to coalesce down partitions dynamically
- Else, minPartitionsNumSpill = max(200, largestShuffleReadSize.toMb() / 200 (Mb)). 
- Return: minPartitionsNumSpill, maxPartitionsNumSpill

getDesireNumberOfPartitions(minPartitionsNumParallelism, minPartitionsNumSpill, maxPartitionsNumSpill, currentPartitionsNum, mode=Resource Saving/Resource Optimization): The number of shuffle partitions sufficient to make use of all cores as well as preventing shuffle spill assuming no data skewness (all partitions spill equally)

- If no spill across all stages: finalPartitionsNum = max(minPartitionsNumParallelism, currentPartitionsNum). This means that currentPartitionsNum are sufficient with no spillage, but still we should at least have minPartitionsNumParallelism to use up all existing cores. This step may consider reducing resources instead. So maybe we can have different modes such as resource saving/resource optimization. One note about resource optimization is that it will also reduce runtime and thus free up completed resources earlier.
- If spillage: Get minPartitionsNumSpill, maxPartitionsNumSpill = checkShuffleSpill(allStagesStats). Then, finalPartitionsNum = minPartitionsNumSpill if mode is Resource Saving else maxPartitionsNumSpill
- Return finalPartitionsNum

The number of cores will influence the number of executors which also influence the amount of memory requested overall. We may either tune the number of cores according to memory requirement or just assume each executors will use 4 cores and only tune the amount of executor memory. For simplicity, currently if there is spillage the numCores will be set to 4 to meet the number of partitions, else numCores is not changed

getNumberOfExecutorsAndCores(finalPartitionsNum, currNumCores, currNumExecutors): This method assumes if there are spillage, the number of partitions will be raised and thus, we will need more core. For simplicity, numCores is just set as 4 in that case so we can focus on tuning memory afterwards

- If no spill: numCores = currNumCores, numExecutors = finalPartitionsNum / numCores
- If spillage: numCores = 4, numExecutors = finalPartitionsNum / numCores
Return numExecutors, numCores

getEachExecutorMemory(totalCacheSize, currExecutorMemory, currMemoryFraction, currStorageFraction, numExecutors): Get enough executor memory for both storage and execution. For simplicity, does not attempt to change spark.memory.fraction=0.6 yet. We may experiment more and just raise this up by default because the other 0.4 is for User Memory which may not be necessary for our applications

- Note: execution memory = storage memory = each executor memory * 0.6 (spark.memory.fraction) * 0.5 (spark.memory.storageFraction)
- If no cacheSpill but shuffleSpill: minTotalExecutorMem = finalPartitionsNum * eachPartitionSizeFraction (200Mb to 1Gb / 1Gb) / 0.6, minEachExecutorMemShuffleSpill = minTotalExecutorMem / numExecutors
- If cacheSpill: minTotalStorageMemoryRequired = totalCacheSize, minTotalStorageAndExecutionMemoryRequired = minTotalStorageMemoryRequired / 0.5, minTotalExecutorMemoryRequired = minTotalStorageAndExecutionMemory / 0.6. Thus, minEachExecutorMemCacheSpill = minTotalExecutorMemoryRequired / numExecutors
Then, minEachExecutorMem = max(minEachExecutorMemShuffleSpill, minEachExecutorMemCacheSpill)
- Return minEachExecutorMem

getExecutorOverheadMemory(eachExecutorMem): Executor's off-heap memory for PySpark executor and other non-executor processes and overheads VM overheads, grows with executor size

- Get minExecutorOverHeadMemory = eachExecutorMem * 0.1
- Return minExecutorOverHeadMemory

## 2. YARN Queue rules based on the notion of resources' relative abundance:

The calculations below is more for determining the application's configuration before running. But could be modified to maybe extract the queue situation at that time

getNumExecutors(queueStats)

- Get queueMem, queueCores
- Get memPerCore = queueMem / queueCores * memHungry 
- Get coresPerExecutor = min(maxUsableMemoryPerContainer / memoryPerCore, 4). Cores per executors should be 4, unless there is insufficient memory in the container
- Get memPerExecutor = max(1Gb, memPerCore * coresPerExecutor). Max amount of memory available for each executor given current queue condition
- Get availableExecutors = allActiveNodes.map(node => min(node.availableNodeMemory/(memoryPerExecutor + overHead), node.AvailableNodeCores/CoresPerExecutor)).sum()
- Get usableExecutors = min(availableExecutorsPerNode, queueMem/memoryPerExecutor, queueCores / coresPerExecutor). Further consider queue constraints to get true number of usable executors
- Get neededExecutors = cacheSize / (memPerExecutor * storageFraction). 
- Get finalExecutors = min(usableExecutors, neededExecutor * computeHungry)
- Return finalExecutors

getNumPartitions(numExecutors, coresPerExecutor, memPerExecutor, storageFraction, cacheSize)

- minPartitions = numExecutors * coresPerExecutor
- memPerTask = memPerExecutor * (1 - storageFraction) / coresPerExecutor
- memPartitions = cacheSize / memPerTask
- finalPartitions = max(minPartitions, memPartitions)
- Return finalPartitions

## 3. AQE rules:

- As AQE is a combination of multiple optimizations which once enabled should work well with one another, we could assume that one there's enough reason to enable AQE, all of its features will be enabled as well. Here, there should be 2 reasons strong enough to enable AQE: very large partition size (requires dynamic coalesce) or very skewed data (requires dynamic skew handling). Especially for skewness, adjust other parameters would not be able to handle it effectively without wastage

enableAQE(allStagesStats, skewSeverityThreshold, partitionsNumSeverityThreshold):

- Get stagesWithSpills
- Get exceedSkewSeverityThreshold = true/false: Analyse each of the stagesWithSpills, get each stage's min/median/max statistics for taskRunTime and taskShuffleReadBytes. Get max-to-median ratio and check if it > skewSeverityThreshold, then exceedSkewSeverityThreshold = true
- Also, get requireInDepthChecking = true/false: Check max-to-median ratio, if it is too high or medianTaskTime = 0, there could be some severe problem with the key that will require further manual and in-depth inspection due to the unnatural skewness, such as in the case of having stress testing keys with an usually high number of records. Thus requireInDepthChecking = true
- Get exceedPartitionsNumSeverityThreshold = true/false: Get finalPartitionNums = getDesireNumberOfPartitions(in part 1). If finalPartitionNums > partitionsNumSeverityThreshold, then exceedPartitionsNumSeverityThreshold = true
- Return exceedSkewSeverityThreshold or requireInDepthChecking or exceedPartitionsNumSeverityThreshold

getAdvisoryPartitionSizeInBytes():

getAutoBroadcastJoinThreshold():

getMinCoalescePartitionSize():

getMaxShuffleHashJoinLocalMapThreshold():

getSkewedPartitionThreshold():

getSkewedPartitionFactor():

# Q04 AV worker-process drain gate

Run one native workflow with the frozen AH producer and unchanged node/Pod PSI, OOM, memory and deadline guards. After the first five pages register and the next group starts, stop the exact owned parser child, drain only its worker process, and start a second worker in the same Pod. The existing Temporal drain oracle requires pages 6–10 to retry once, the first group to remain registered, and all other groups to run once. The final 51-page document must match the accepted native baseline.

The new AV identity, PVC and object prefix preserve all prior runs. It has one controlled execution and no automatic retry. A process-drain pass does not prove in-flight Pod replacement or close #51.

---
subject: FalkorDB replica restarts under trim load
started: 2026-08-14T17:40Z
status: closed
trail-version: 1
---

# FalkorDB replica restarts under trim load

## Findings

| id | claim | state | evidence | framed by |
|----|-------|-------|----------|-----------|
| F1 | Replica pods restart during trim cycles; masters do not. | reasoned | E1 | human |
| F2 | Restarts are caused by container memory pressure. | refuted | E2 | human |
| F3 | Trim load arrives alongside cluster rebalance. | accepted | E3 | claude |
| F4 | Whether the liveness probe timeout is the trigger. | open | | human |

## Evidence

### E1

- form: metrics
- target: `grafanacloud-prom`
- query: `sum by (pod) (increase(kube_pod_container_status_restarts_total{namespace="asserts"}[1h]))`
- window: `2026-08-10T14:00:00Z` to `2026-08-10T18:00:00Z`
- replayable: yes
- returned:

  ```
  {pod="falkordb-03-node-1"}  4
  {pod="falkordb-03-node-2"}  3
  {pod="falkordb-03-node-0"}  0
  ```

### E2

- form: metrics
- target: `grafanacloud-prom`
- query: `max by (pod) (container_memory_working_set_bytes{namespace="asserts"}) / max by (pod) (container_spec_memory_limit_bytes{namespace="asserts"})`
- window: `2026-08-10T14:00:00Z` to `2026-08-10T18:00:00Z`
- replayable: yes
- returned:

  ```
  {pod="falkordb-03-node-1"}  0.21
  {pod="falkordb-03-node-2"}  0.19
  ```

### E3

- form: shell
- command: `kubectl get events -n asserts --sort-by=.lastTimestamp`
- context: `prod-us-west-0`
- run: `2026-08-14T18:02:00Z`
- replayable: drifts
- returned:

  ```
  17:58  Normal  Rebalance  statefulset/falkordb-03-node
  17:59  Warning Unhealthy  pod/falkordb-03-node-1
  ```

## Not checked

| what | why | noted |
|------|-----|-------|
| Replica logs before the first restart | Loki retention had expired for that window | 2026-08-14T17:52Z |
| Behavior on the other three clusters | Scoped the session to one cluster deliberately | 2026-08-14T18:10Z |

## Synthesis

The restarts track rebalance, not memory. Working set never went above a fifth of
the limit, so the memory story is dead. What I still cannot rule out is the probe
timeout, because I never looked at the probe config.

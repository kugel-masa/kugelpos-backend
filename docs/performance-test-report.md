# Performance test report

Results from the standard procedure in `.claude/commands/perf-test.md`: 300 users,
3 minutes, 310 terminals, JWT auth, `docker-compose.prod.yaml`, Redis flushed and
the stack fully restarted before each run.

The procedure refers to this file for baseline comparison. It did not exist until
now — the only stored results were a 40-user run from 2026-06-15, which is not
comparable at 300 users. This is the first baseline.

## Environment

Local, 6 CPU / 16 GB. At 300 users the stack is saturated: average response times
are in seconds and the database and Dapr are the bottleneck. **The absolute
numbers are not a service-level target** — they exist so that two builds measured
the same way can be compared.

Variability quoted by the procedure, for repeated runs of the same build:
average ±15–19%, req/s ±0.5%.

## 2026-08-25 — request-body ceiling (#195)

Does buffering every request body outermost, ahead of authentication, cost
throughput? `RequestBodySizeLimitMiddleware` reads each body in full before the
application sees it, on all seven services.

| metric | before (`main`, 008223d) | after (#195 + #200) | delta |
|---|---:|---:|---:|
| requests | 5,897 | 6,140 | +4.1% |
| **failures** | **0** | **0** | — |
| average | 5,268 ms | 4,967 ms | −5.7% |
| p50 | 5,600 ms | 4,900 ms | −12.5% |
| p95 | 8,600 ms | 8,200 ms | −4.7% |
| p99 | 19,000 ms | 21,000 ms | +10.5% |
| **req/s** | **32.97** | **34.27** | **+3.9%** |

Raw results: `services/cart/performance_tests/results/Custom_300users_20260825_024915_*`
(before) and `Custom_300users_20260825_025619_*` (after).

### Reading

**No measurable throughput cost.** req/s moved +3.9%, and average, p50 and p95 all
moved in the faster direction. That is not evidence the change made anything
faster: the ±0.5% req/s figure above is for repeated runs of one build, and these
two runs rebuilt the images and recreated the data. The honest conclusion is that
the cost, if any, is below what this setup can resolve.

**Zero failures matters more than the timings.** Every request was buffered
outermost, cart ran with a 4 MB ceiling and the cart size budget active, and not
one legitimate request was answered 413 or 409.

### What this does not measure

The perf scenario sends small bodies — hundreds of bytes to a few kilobytes. At
that size the extra buffering disappears against a saturated database. It says
nothing about large bodies, which were measured separately for #195:

- a 999-line transaction carries an 894 KB snapshot on every mutating request
- serialising it costs 7.5 ms, and the cart size budget (#200) makes a guarded
  request pay it twice — worst case +7.5 ms on one request, under 1 ms for an
  ordinary basket

Those numbers are in the #195 and #200 pull requests.

## Reproducing

```bash
# per build under test
cd services && docker compose -f docker-compose.prod.yaml down && docker compose -f docker-compose.prod.yaml up -d
# wait for all seven /health to report healthy
cd cart/performance_tests/scripts && bash run_perf_test.sh setup 310
docker exec redis redis-cli FLUSHALL
bash run_perf_test.sh custom 300 3m
```

Note: building an image for an older commit needs the `kugel_common` wheel that
commit pins. `services/commons/dist/` is gitignored and older wheels get cleaned,
so the wheel has to be rebuilt from that commit's source — and because a rebuilt
wheel is not byte-identical, the sha256 in each `Pipfile.lock` has to be updated
before `pipenv install --deploy` will accept it.

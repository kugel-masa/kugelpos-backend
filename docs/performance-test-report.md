# Performance test report

Results from the standard procedure in `.claude/commands/perf-test.md`: 300 users,
3 minutes, 310 terminals, JWT auth, `docker-compose.prod.yaml`, Redis flushed and
the stack fully restarted before each run.

The procedure refers to this file for baseline comparison. It did not exist until
now — the only stored results were a 40-user run from 2026-06-15, which is not
comparable at 300 users.

## Before running: two traps

**`docker-compose.prod.yaml` needs `SNAPSHOT_HMAC_KEYS`.** It is declared
`${SNAPSHOT_HMAC_KEYS:?...}`, there is no `services/.env` in a fresh checkout, and
`docker compose up` therefore fails outright. Export it first.

**Building an image does not replace a running container.** `build.sh` moves the
`:latest` tag; containers keep the image they started with. If the compose restart
silently failed, the stack keeps serving the *previous* build and every health
check still passes — so a run can look valid while measuring the wrong code.

Check the image id, not the health endpoint:

```bash
docker inspect services-cart-1 --format '{{.Image}}'
docker image inspect masakugel/kugelpos.cart:latest --format '{{.Id}}'
```

They must match. See the retracted run below for what happens when they do not.

## Environment

Local, 6 CPU / 16 GB. At 300 users the stack is saturated: average response times
are in seconds and the database and Dapr are the bottleneck. **The absolute
numbers are not a service-level target** — they exist so that two builds measured
the same way can be compared.

Variability quoted by the procedure, for repeated runs of the same build:
average ±15–19%, req/s ±0.5%.

## 2026-08-25 — request-body ceiling (#195): RETRACTED, invalid

An attempt to answer whether buffering every request body outermost costs
throughput. **The results were not measuring what they claimed and are withdrawn.**

`docker compose -f docker-compose.prod.yaml up -d` failed on the missing
`SNAPSHOT_HMAC_KEYS` for both runs, with its output discarded and its exit status
unchecked. The containers left running from an earlier `start.sh` answered every
health check, so both runs proceeded — against the same containers, started at
02:41 from an image built before either run:

```
container started : 02:41:29   image sha256:a7c06f92...
run 1 ("before")  : 02:52      same container
run 2 ("after")   : 02:59      same container
```

So both numbers came from one build, and the +3.9% req/s reported at the time was
run-to-run variance and nothing else. The run also used `docker-compose.yaml`
rather than the `docker-compose.prod.yaml` the procedure specifies.

Raw files remain at `services/cart/performance_tests/results/Custom_300users_20260825_024915_*`
and `Custom_300users_20260825_025619_*`. They are two samples of one build, which
is the only thing they can honestly be used for.

Kept rather than deleted because the failure mode is the useful part: a health
check cannot tell you which build it is talking to.

## What is measured, separately from this

Large-body behaviour was measured directly for #195 and #200 and does not depend
on this harness:

- a 999-line transaction carries an 894 KB snapshot on every mutating request
- serialising it costs 7.5 ms, and the cart size budget (#200) makes a guarded
  request pay it twice — worst case +7.5 ms on one request, under 1 ms for an
  ordinary basket

Those numbers are in the #195 and #200 pull requests. Note that the perf scenario
sends bodies of hundreds of bytes to a few kilobytes, so even a valid run of it
would say little about the large-body case.

## Reproducing

```bash
export SNAPSHOT_HMAC_KEYS='dev-v1:a3VnZWxwb3MtZGV2LXNuYXBzaG90LWtleS0zMmJ5dGU='
cd services
docker compose -f docker-compose.prod.yaml down
docker compose -f docker-compose.prod.yaml up -d          # check the exit status
docker inspect services-cart-1 --format '{{.Image}}'       # must match :latest
# wait for all seven /health to report healthy
cd cart/performance_tests/scripts && bash run_perf_test.sh setup 310
docker exec redis redis-cli FLUSHALL
bash run_perf_test.sh custom 300 3m
```

Building an image for an older commit needs the `kugel_common` wheel that commit
pins. `services/commons/dist/` is gitignored and older wheels get cleaned, so the
wheel has to be rebuilt from that commit's source — and because a rebuilt wheel is
not byte-identical, the sha256 in each `Pipfile.lock` has to be updated before
`pipenv install --deploy` will accept it.

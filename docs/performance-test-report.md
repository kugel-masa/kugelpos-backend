# Performance test report

Results from the standard procedure in `.claude/commands/perf-test.md`: 300 users,
3 minutes, 310 terminals, JWT auth, `docker-compose.prod.yaml`, Redis flushed and
the stack fully restarted before each run.

The procedure refers to this file for baseline comparison. It did not exist until
now — the only stored results were a 40-user run from 2026-06-15, which is not
comparable at 300 users.

## Before running: five ways to get the wrong answer

The first four fail quietly, with all seven health checks green.

**1. `docker-compose.prod.yaml` needs `SNAPSHOT_HMAC_KEYS`.** Declared
`${SNAPSHOT_HMAC_KEYS:?...}`, with no `services/.env` in a fresh checkout, so
`docker compose up` fails outright. Check the exit status — if containers from an
earlier run are still up, they answer every health check.

**2. Building an image does not replace a running container.** `build.sh` moves the
tag; containers keep the image they started with. Compare image ids, not health:

```bash
docker inspect kugelpos-cart-prod --format '{{.Image}}'
docker image inspect kugelpos-cart:prod --format '{{.Id}}'
```

**3. `build.sh` alone does not build the images this compose file uses.** It
produces `masakugel/kugelpos.cart:latest`; `docker-compose.prod.yaml` runs
`kugelpos-cart:prod`. Only `build.sh --prod` produces those. Without it the stack
serves whatever `:prod` images happen to be on the machine — in one case, images
twelve days old.

**4. Cart refuses to start on the development key.** The key committed to this
repository is rejected unless `SNAPSHOT_ALLOW_INSECURE_KEY=true`; cart crash-loops
while the other six stay healthy, and setup fails with a 500 from the terminal
service that reads as a connection error. Generate a real key:

```bash
export SNAPSHOT_HMAC_KEYS="$(python3 -c "import base64,os;print('perf-v1:'+base64.b64encode(os.urandom(32)).decode())")"
```

**5. `--prod` and a plain build do not compose.** The `--prod` path copies
`commons/dist` into each service directory for build context and deletes it
afterwards; the plain path expects that copy to already be there. So a plain
`build.sh` straight after a `build.sh --prod` fails on `pipenv install --deploy`
with a missing wheel. Run `./scripts/run_copy_common.sh` in between. This one at
least fails loudly.

## Environment

Local, 6 CPU / 16 GB. At 300 users the stack is saturated: average response times
are in seconds and the database and Dapr are the bottleneck. **The absolute
numbers are not a service-level target** — they exist so that two builds measured
the same way can be compared.

Variability quoted by the procedure, for repeated runs of the same build:
average ±15–19%, req/s ±0.5%.

## 2026-08-25 — request-body ceiling (#195) and everything stacked on it

Does buffering every request body outermost, ahead of authentication, cost
throughput? `RequestBodySizeLimitMiddleware` reads each body in full before the
application sees it, on all seven services.

Measured `main` (008223d) against every change stacked on it — #195, #197, #199,
#200, #202 — with the preconditions below checked mechanically on both runs.

| metric | main | with the changes | delta |
|---|---:|---:|---:|
| requests | 16,531 | 16,534 | +0.0% |
| **failures** | **0** | **0** | — |
| average | 241.3 ms | 240.2 ms | −0.4% |
| p50 | 98 ms | 110 ms | +12.2% |
| p95 | 920 ms | 900 ms | −2.2% |
| p99 | 1,700 ms | 1,700 ms | +0.0% |
| **req/s** | **92.15** | **92.24** | **+0.1%** |

Raw results: `services/cart/performance_tests/results/Custom_300users_20260825_063023_*`
(main) and `Custom_300users_20260825_062044_*` (with the changes).

### Reading

**No measurable cost.** req/s within 0.1%, average within 0.4%, p99 identical, and
the two runs completed 16,531 and 16,534 requests. The p50 gap (98 → 110 ms) is
12 ms at the bottom of the distribution while nothing else moves, which reads as
noise rather than signal.

**Zero failures.** Every request buffered outermost, cart running with a 4 MB
ceiling and the cart size budget active, CORS relocated and the unhandled-500
middleware in place on all seven services — and not one legitimate request
answered 413 or 409.

### An earlier attempt at this was invalid

Before the preconditions above were checked, a run reported +3.9% req/s at
33–34 req/s. Both of its samples came from one build, and from the wrong compose
file — that is roughly a third of the throughput measured here, because
`docker-compose.prod.yaml` runs cart with four uvicorn workers and the dev compose
runs one. The raw files (`Custom_300users_20260825_024915_*` and
`..._025619_*`) are two samples of a single build and nothing more.

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
./scripts/build.sh --prod                                  # note --prod
cd services
docker compose -f docker-compose.prod.yaml down            # check the exit status
docker compose -f docker-compose.prod.yaml up -d           # check the exit status
docker inspect kugelpos-cart-prod --format '{{.Image}}'    # must equal kugelpos-cart:prod
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

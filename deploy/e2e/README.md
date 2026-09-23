# Whole-stack end-to-end tests

`test_stack.py` starts the production compose stack from locally built images,
with a throwaway Postgres in place of Neon, and checks it from the outside:
routing through Caddy, migrations, authentication on the API, the frontend, the
retrieval service, container hardening and memory limits.

```bash
# build the three images first (see ../README.md), tagged :local
docker build -t draftly-backend:local ../../backend
docker build -t draftly-frontend:local --build-arg NEXT_PUBLIC_API_BASE_URL=https://localhost ../../frontend
docker build -t draftly-retrieval:local -f ../retrieval/Dockerfile \
  --build-context deploy=../retrieval ../../../draftly

# run (uses the backend's uv environment for pytest)
cd ../../backend && uv run pytest ../deploy/e2e -v -p no:cacheprovider
```

The stack is torn down afterwards. Set `E2E_KEEP_STACK=1` to leave it running.
No Clerk or Gemini keys are used, so sign-in and generated answers are outside
this suite; the API is checked for rejecting unauthenticated calls.

# Running in Docker

If you'd rather not install Python/dependencies locally, there's a dev container with everything pre-installed:

```bash
make docker-build   # build the image (first time, or after requirements.txt changes)
make docker-run      # start Jupyter Lab at http://localhost:8888
make docker-stop     # stop the container (from another terminal, if docker-run is running in the foreground)
```

The repo is mounted into the container, so edits you make locally are reflected immediately — no rebuild needed unless `requirements.txt` changes. `requirements.txt` holds the project's runtime dependencies (NLP libraries, etc.); `requirements-dev.txt` is separate and only used for local linting/formatting tooling outside Docker.

Notebooks autosave to disk every 15 seconds while you're editing (configured in `docker/jupyter_overrides.json`), so changes land in your repo folder without a manual save. Autosave only writes to disk, though — you still need to `git add`/commit when you want a checkpoint in history.

### Fixing "403 Forbidden" errors in JupyterLab

If every action in the browser (opening files, creating new ones, saving) starts failing with a 403, it's almost always a stale `_xsrf` cookie: each time the container restarts, it generates a new cookie secret, but your browser may still be holding a cookie from a previous instance for that same address.

To fix it:
1. Close any open `127.0.0.1:8888` / `localhost:8888` tabs.
2. Clear cookies for that address (DevTools → Application → Cookies → right-click the `127.0.0.1:8888` entry → Clear), or just open the link in a new **incognito/private window** to avoid the stale cookie entirely.
3. Grab the current URL (with its token) from the running container's logs and open that:
   ```bash
   docker logs nlp-dev 2>&1 | grep -m1 "127.0.0.1:8888/lab?token"
   ```
4. Always access JupyterLab via the **same hostname** (either `127.0.0.1` or `localhost`, not both interchangeably) to avoid re-triggering this.

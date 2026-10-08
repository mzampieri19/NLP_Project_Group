FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Autosave every 15s instead of JupyterLab's default 120s, so changes in the
# mounted volume hit disk (and are visible to git) without a manual Ctrl+S.
COPY docker/jupyter_overrides.json /usr/local/share/jupyter/lab/settings/overrides.json

COPY . .

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]

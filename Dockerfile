FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    RELOAD=false \
    ALLOW_UNVERIFIED_JWT=false \
    ALLOW_LOCAL_SUPER_ADMIN=false

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 storyweaver \
    && useradd --uid 10001 --gid storyweaver --no-create-home storyweaver \
    && mkdir /app/stories \
    && chown storyweaver:storyweaver /app/stories

COPY main.py openai_compat.py regeneration.py ./
COPY static/index.html ./static/index.html

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/ping', timeout=4); assert r.status == 200 and r.read() == b'OK'"

CMD ["python", "main.py"]

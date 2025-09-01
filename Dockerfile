FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/   

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN uv venv /opt/venv                 
ENV VIRTUAL_ENV=/opt/venv             
ENV PATH="/opt/venv/bin:$PATH"        
RUN uv pip install -r requirements.txt 

COPY *.py ./
COPY  templates ./templates/
COPY  static ./static
COPY  assets ./assets
COPY  .env ./

RUN mkdir output_files
RUN mkdir input_files
RUN mkdir diff

EXPOSE 5100
EXPOSE 8050

CMD [ "uv", "run" , "./webNetworkgraph.py" ]  


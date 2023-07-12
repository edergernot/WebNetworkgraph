FROM python:3.11-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY  templates ./templates/
COPY  static ./static
COPY  assets ./assets

RUN mkdir output_files
RUN mkdir input_files

EXPOSE 5100
EXPOSE 8050


CMD [ "python", "./webNetworkgraph.py" ]



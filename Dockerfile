FROM python:3.8.8-slim-buster

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN mkdir -p /root/.streamlit

RUN bash -c 'echo -e "\
[general]\n\
email = \"\"\n\
" > /root/.streamlit/credentials.toml'


ENV STREAMLIT_SERVER_PORT=80
EXPOSE 80

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip &&\
    python -m pip install --no-cache-dir -r requirements.txt

COPY .streamlit/config.toml /root/.streamlit/config.toml

COPY . /app
WORKDIR /app

ENTRYPOINT [ "streamlit" ]
CMD ["run", "CVAnalyzer.py"]

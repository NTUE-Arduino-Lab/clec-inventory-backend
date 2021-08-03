FROM python:3.8-slim
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install unixodbc -y \
    && apt-get install unixodbc-dev -y \
    && apt-get install --reinstall build-essential -y \
    && apt-get install gnupg2 -y \
    && apt-get install curl -y \
    && apt-get install libasound2 -y\
    && apt-get install libssl-dev -y

WORKDIR /user/src/app
COPY 'requirements.txt' .

RUN pip3 install --trusted-host pypi.python.org -r requirements.txt

COPY . .

ENV LISTEN_PORT 80

EXPOSE 80
CMD [ "python3","-u","app.py" ]
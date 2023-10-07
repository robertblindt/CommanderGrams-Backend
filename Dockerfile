FROM --platform=linux/amd64 python:3.9.13

RUN apt-get update; apt-get clean
RUN useradd apps
RUN mkdir -p /home/apps && chown apps:apps /home/apps
ENV CHROME_VERSION = "114.0.5735.91"
# Adding trusting keys to apt for repositories
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -

# Adding Google Chrome to the repositories
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# Updating apt to see and install Google Chrome
RUN apt-get -y update

# Magic happens
RUN apt-get install -y google-chrome-stable

# Installing Unzip
RUN apt-get install -yqq unzip


# install chromedriver
# THIS CHROME DRIVER IS TOO OLD!
# RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
# RUN unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# RUN wget -O /tmp/chromedriver.zip https://edgedl.me.gvt1.com/`curl -sS edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/117.0.5938.149/linux64`/chromedriver-linux64.zip
RUN wget -O /tmp/chromedriver-linux64.zip https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/117.0.5938.149/linux64/chromedriver-linux64.zip

RUN unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/

# RUN dbus-uuidgen > /var/lib/dbus/machine-id
# RUN mkdir -p /var/run/dbus
# RUN dbus-daemon --config-file=/usr/share/dbus-1/system.conf --print-address


WORKDIR /app

COPY requirements.txt requirements.txt 
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pretty sure this is wrong.  I normally start this with flask --debug run.  gunicorn app:app is what starts it on render I think.
# CMD ["gunicorn", "app:app"]
CMD ["flask", "run"]
# EXPOSE 5000/tcp
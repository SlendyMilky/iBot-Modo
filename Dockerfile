FROM python:alpine3.18

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies:
RUN mkdir /iBot-Modo
WORKDIR /iBot-Modo
ADD . /iBot-Modo/
RUN pip install -U python-dotenv
RUN pip install -r requirements.txt

# Run the application:
CMD ["python3", "/iBot-Modo/ibot-modo.py"]`
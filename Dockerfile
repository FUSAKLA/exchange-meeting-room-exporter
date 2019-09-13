FROM python:3.6-buster

COPY requirements.txt /exchange-meeting-room-exporter/

RUN pip install -r /exchange-meeting-room-exporter/requirements.txt

COPY exchange-meeting-room-exporter.py /exchange-meeting-room-exporter/

WORKDIR /exchange-meeting-room-exporter

EXPOSE 8000

ENTRYPOINT ["python3", "exchange-meeting-room-exporter.py"]

CMD ["--help"]

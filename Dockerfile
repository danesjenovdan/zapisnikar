FROM python:3.13

# RUN /usr/local/bin/python -m pip install --upgrade pip

RUN mkdir /app
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# # add node
# RUN apk add --update nodejs npm

COPY . /app

# RUN python3 manage.py compilemessages

EXPOSE 8000

# ENV DJANGO_SETTINGS_MODULE=parladata_project.settings.k8s

CMD exec python manage.py runserver 0.0.0.0:8000

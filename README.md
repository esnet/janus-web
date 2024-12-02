# JANUS Web Application
User-driven DTN endpoint provisioning with Janus

### Janus Web Setup

- Clone the Janus Web Repository:
```
git clone https://github.com/esnet/janus-web.git
cd janus-web
```

- Install Required Packages:
```
pip3 install -r requirements.txt
```

- Set Up the Local Database:
```
python3 webapp/manage.py migrate
```

- Create a Django Admin User Account:
```
python3 webapp/manage.py createsuperuser
```

- Start the Django Development Web Server:
```
python3 webapp/manage.py runserver
```
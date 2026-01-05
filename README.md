# bestarion-adk-example

## Prerequisites
Run local Jenkins for testing
```bash
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

Getting Jenkins admin password
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

## Run Agent
```bash
adk web
```